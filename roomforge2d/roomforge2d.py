
import tkinter as tk
import ttkbootstrap as ttkb
from tkinter import simpledialog, messagebox
import math

# Constants
BASE_SCALE = 40      # pixels per foot
ZOOM_STEP   = 1.2
MIN_ZOOM    = 0.5
MAX_ZOOM    = 5.0


# Dialogs
class OptionDialog(tk.Toplevel):
    """Generic radio dialog for options."""
    def __init__(self, parent, title, prompt, options):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.result = None
        self.var = tk.StringVar(value=options[0][0])
        
        tk.Label(self, text=prompt).pack(padx=10, pady=5)
        for value, label in options:
            tk.Radiobutton(self, text=label, variable=self.var, value=value)\
              .pack(anchor='w', padx=20)
        btns = tk.Frame(self); btns.pack(pady=5)
        tk.Button(btns, text='OK',    command=self.on_ok).pack(side='left',  padx=5)
        tk.Button(btns, text='Cancel', command=self.destroy).pack(side='right', padx=5)
        self.grab_set()
        parent.wait_window(self)

    def on_ok(self):
        self.result = self.var.get()
        self.destroy()

class RoomPlanner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.style = ttkb.Style('minty')  # Set a default theme
        self.title('RoomForge2d version 1.1')
        self.geometry('900x600')
        self.state('zoomed')  # start maximized

        # State
        self.zoom            = 1
        self.mode            = None
        self.points          = []
        self.wall_lines      = []
        self.wall_labels     = []
        self.temp_line       = None
        self.temp_label      = None
        self.windows         = {}  # tag -> {'wall_idx','length_ft','id'}
        self.furniture       = {}  # tag -> {'id','name','shape','w','h','d','angle'}
        self.actions         = []
        self.new_item        = None
        self.wall_tag_map    = {}  # map wall tags to indices

        # Move/drag state
        self.selected_window = None
        self.selected_item   = None
        self.drag_data       = {}
        self.move_outline    = None

        # Toolbar
        tb = ttkb.Frame(self, bootstyle='light')
        tb.pack(side='left', fill='y',padx=5, pady=5)
        for text, cmd in [
            ('Draw Room',     lambda: self.set_mode('draw')),
            ('Undo',          self.undo_action),
            ('Clear Room',    self.clear_room),
            #('Delete Wall',   lambda: self.set_mode('delete_wall')),
            ('Add Window',    lambda: self.set_mode('add_window')),
            ('Add Furniture', self.prepare_furniture),
            ('Select/Edit',   lambda: self.set_mode('select')),
        ]:
           ttkb.Button(tb, bootstyle='info-outline',text=text, command=cmd).pack(fill='x', pady=2)

        ttkb.Button(tb, bootstyle='info-outline', text='Zoom In',  command=self.zoom_in).pack(fill='x', pady=2)
        ttkb.Button(tb, bootstyle='info-outline',text='Zoom Out', command=self.zoom_out).pack(fill='x', pady=2)

        #message:
        messagebox.showinfo("Welcome to RoomForge2D!", f"\nRemember: Hold shift to make a straight line during wall building and press enter when moving furniture/window")

        # Canvas
        self.canvas = tk.Canvas(self, bg='white')
        self.canvas.pack(side='right', expand=True, fill='both')
        # Panning
        self.canvas.bind('<ButtonPress-2>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B2-Motion>',     lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))

        # Status bar
        self.status = tk.Label(self, text='Mode: (none)', bd=1, relief='sunken', anchor='w')
        self.status.pack(side='bottom', fill='x')

        # Global bindings
        self.bind_all('<Escape>',    lambda e: self.reset_draw())
        self.bind_all('<Control-z>', lambda e: self.undo_action())

        #focus window
        "tells focus is in main window = mostly for bind while in draw mode"
        self.after(100, lambda: (self.focus_force(), self.canvas.focus_set()))

    # --- Preview vs. Draw Cleanup ---
    def clear_preview(self):
        if self.temp_line:
            self.canvas.delete(self.temp_line)
            self.temp_line = None
        if self.temp_label:
            self.canvas.delete(self.temp_label)
            self.temp_label = None

    def reset_draw(self):
        """Abort wall-draw: clear preview + reset points."""
        self.clear_preview()
        self.points.clear()

    # stub for backward compatibility
    def clear_temps(self):
        self.clear_preview()

    # --- Mode Switching ---
    def set_mode(self, mode):
        # cancel any in-flight move/edit
        self.finish_move_wall()
        self.finish_move_window()
        self.finish_move_furn()

        self.mode = mode
        self.status.config(text=f'Mode: {mode}')
        self.reset_draw()

        self.canvas.unbind('<Button-1>')
        self.canvas.unbind('<Motion>')
        if mode == 'draw':
            self.canvas.bind('<Motion>',   self.preview_wall)
            self.canvas.bind('<Button-1>', self.add_wall_point)
        elif mode == 'delete_wall':
            self.canvas.bind('<Button-1>', self.delete_wall)
        elif mode == 'add_window':
            self.canvas.bind('<Button-1>', self.add_window)
        elif mode == 'add_furn':
            self.canvas.bind('<Button-1>', self.place_furniture)
        elif mode == 'select':
            self.canvas.bind('<Button-1>', self.select_item)

        self.canvas.focus_set()

    # --- Zoom ---
    def zoom_in(self):  self._zoom(ZOOM_STEP)
    def zoom_out(self): self._zoom(1/ZOOM_STEP)
    def _zoom(self, factor):
        new = self.zoom * factor
        if MIN_ZOOM <= new <= MAX_ZOOM:
            self.zoom = new
            self.canvas.scale('all', 0, 0, factor, factor)

    # --- Undo & Clear ---
    def undo_action(self):
        if not self.actions:
            return
        act = self.actions.pop()
        if   act['type']=='wall':   self._undo_wall()
        elif act['type']=='window': self._undo_window(act['tag'])
        elif act['type']=='furn':   self._undo_furn(act['tag'])

    def _undo_wall(self):
        if self.wall_lines:
            l   = self.wall_lines.pop()
            lbl = self.wall_labels.pop()
            # pop a point only if it exists
            if self.points:
                self.points.pop()
            if l:
                self.canvas.delete(l)
            if lbl:
                self.canvas.delete(lbl)

    def _undo_window(self, tag):
        info = self.windows.pop(tag, None)
        if info:
            self.canvas.delete(info['id'])

    def _undo_furn(self, tag):
        info = self.furniture.pop(tag, None)
        if info:
            self.canvas.delete(info['id'])

    def clear_room(self):
        for l in self.wall_lines:    self.canvas.delete(l)
        for lbl in self.wall_labels: self.canvas.delete(lbl)
        for w in self.windows.values():   self.canvas.delete(w['id'])
        for f in self.furniture.values(): self.canvas.delete(f['id'])
        self.points.clear()
        self.wall_lines.clear()
        self.wall_labels.clear()
        self.windows.clear()
        self.furniture.clear()
        self.actions.clear()

    # --- Wall Drawing ---
    def preview_wall(self, e):
        if not self.points: return
        x0,y0 = self.points[-1]
        x1,y1 = e.x,e.y
        if e.state & 0x0001:
            if abs(x1-x0)>abs(y1-y0): y1=y0
            else: x1=x0
        self.clear_preview()
        self.temp_line = self.canvas.create_line(x0,y0,x1,y1, fill='gray', dash=(4,2))
        length = math.hypot(x1-x0,y1-y0)/(BASE_SCALE*self.zoom)
        mx,my = (x0+x1)/2,(y0+y1)/2
        self.temp_label = self.canvas.create_text(mx,my-10, text=f'{length:.1f} ft', fill='gray')

    def add_wall_point(self, e):
        self.clear_preview()
        x,y = e.x,e.y
        if self.points and (e.state & 0x0001):
            x0,y0 = self.points[-1]
            dx,dy = x-x0,y-y0
            if abs(dx)>abs(dy): y=y0
            else: x=x0
        self.points.append((x,y))
        if len(self.points)>1:
            x0,y0 = self.points[-2]; idx=len(self.wall_lines)
            tag    = f'wall{idx}'
            line_id= self.canvas.create_line(x0,y0,x,y, width=2, tags=(tag,'wall'))
            length = math.hypot(x-x0,y-y0)/(BASE_SCALE*self.zoom)
            mx,my  = (x0+x)/2,(y0+y)/2
            lbl_id = self.canvas.create_text(mx,my-10, text=f'{length:.1f} ft',
                                             fill='blue', tags=(tag,'wall'))
            self.wall_lines.append(line_id)
            self.wall_labels.append(lbl_id)
            self.actions.append({'type':'wall'})
        else:
            self.wall_lines.append(None)
            self.wall_labels.append(None)

    def delete_wall(self, e):
        for item in reversed(self.canvas.find_overlapping(e.x-2,e.y-2,e.x+2,e.y+2)):
            for t in self.canvas.gettags(item):
                if t.startswith('wall'):
                    idx = int(t[4:])
                    dlg = OptionDialog(self,'Wall Action','Choose action:',
                                       [('move','Move'),('resize','Resize'),('delete','Delete')])
                    act = dlg.result
                    if act=='move':
                        self.start_wall_move(idx,e)
                    elif act=='resize':
                        self.edit_wall(self.wall_lines[idx])
                    elif act=='delete':
                        self._undo_wall()
                    return
    
    def delete_wall_by_index(self, idx):
        if idx < 0 or idx >= len(self.wall_lines):
            print(f"[WARNING] Tried to delete wall with invalid index: {idx}")
            return

        # delete the wall and label from canvas
        line_id = self.wall_lines[idx]
        label_id = self.wall_labels[idx]
        if line_id:  self.canvas.delete(line_id)
        if label_id: self.canvas.delete(label_id)

        # emove from internal lists
        del self.wall_lines[idx]
        del self.wall_labels[idx]
        if len(self.points) > idx + 1:
            del self.points[idx + 1]

        # re-tag remaining walls
        for i, line_id in enumerate(self.wall_lines):
            if line_id:
                self.canvas.itemconfig(line_id, tags=(f'wall{i}', 'wall'))
        for i, label_id in enumerate(self.wall_labels):
            if label_id:
                self.canvas.itemconfig(label_id, tags=(f'wall{i}', 'wall'))


    def start_wall_move(self, idx, e):
        line_id = self.wall_lines[idx]
        self.canvas.itemconfigure(line_id, dash=(4,2))
        self.selected_window = idx
        self.drag_data = {'x':e.x,'y':e.y,'coords':self.canvas.coords(line_id)}
        self.canvas.unbind('<Button-1>')
        self.canvas.bind('<Motion>', self.move_wall)
        self.bind('<Return>',       self.finish_move_wall)

    def move_wall(self, e):
        dx,dy = e.x-self.drag_data['x'], e.y-self.drag_data['y']
        x0,y0,x1,y1 = self.drag_data['coords']
        new = (x0+dx, y0+dy, x1+dx, y1+dy)
        lid = self.wall_lines[self.selected_window]
        self.canvas.coords(lid, *new)
        lbl = self.wall_labels[self.selected_window]
        mx,my = (new[0]+new[2])/2,(new[1]+new[3])/2
        self.canvas.coords(lbl, mx, my-10)

    def finish_move_wall(self, e=None):
        idx = self.selected_window
        if idx is not None:
            lid = self.wall_lines[idx]
            self.canvas.itemconfigure(lid, dash=())
        self.canvas.unbind('<Motion>')
        self.unbind('<Return>')
        self.canvas.bind('<Button-1>', self.select_item)
        self.selected_window = None
        self.drag_data = {}

    def edit_wall(self, line_id):
        x1,y1,x2,y2 = self.canvas.coords(line_id)
        cur = math.hypot(x2-x1,y2-y1)/(BASE_SCALE*self.zoom)
        new = simpledialog.askfloat('Resize Wall','Length (ft):',initialvalue=cur,parent=self)
        if new is None: return
        factor = (new*BASE_SCALE*self.zoom)/math.hypot(x2-x1,y2-y1)
        nx,ny = x1+(x2-x1)*factor, y1+(y2-y1)*factor
        self.canvas.coords(line_id, x1,y1,nx,ny)
        idx = self.wall_lines.index(line_id)
        lbl = self.wall_labels[idx]
        mx,my = (x1+nx)/2,(y1+ny)/2
        self.canvas.coords(lbl, mx, my-10)
        self.canvas.itemconfigure(lbl, text=f'{new:.1f} ft')

    # --- Window ---
    def add_window(self, e):
        for item in reversed(self.canvas.find_overlapping(e.x-2,e.y-2,e.x+2,e.y+2)):
            for t in self.canvas.gettags(item):
                if t.startswith('wall'):
                    idx = int(t[4:])
                    if idx < 0 or idx >= len(self.wall_lines) or self.wall_lines[idx] is None:
                        continue
                    length = simpledialog.askfloat('Add Window','Length (ft):',parent=self)
                    if length is None: return

                    
                    wtag = f'window{len(self.windows)}'
                    self._place_window(idx, e.x, e.y, length, wtag)
                    self.actions.append({'type': 'window', 'tag': wtag})
                    return


    def _place_window(self, idx, mx, my, length, wtag):
        # guard against invalid wall index
        if idx < 0 or idx >= len(self.wall_lines) or self.wall_lines[idx] is None:
            return
        x1,y1,x2,y2 = self.canvas.coords(self.wall_lines[idx])
        seglen = math.hypot(x2-x1,y2-y1)
        ux,uy = (x2-x1)/seglen, (y2-y1)/seglen
        half  = length*BASE_SCALE*self.zoom/2
        p1 = (mx-ux*half, my-uy*half)
        p2 = (mx+ux*half, my+uy*half)
        wtag = f'window{len(self.windows)}'
        wid  = self.canvas.create_line(*p1,*p2, fill='cyan', width=4, tags=(wtag,'window'))
        self.windows[wtag] = {'wall_idx':idx,'length_ft':length,'id':wid}
        self.canvas.tag_bind(wtag,'<Button-1>',lambda ev,t=wtag:self.edit_window(ev,t))

    def edit_window(self, e, tag):
        options = [('move','Move'),('resize','Resize'),('delete','Delete')]
        dlg = OptionDialog(self,'Window Action','Choose action:',options)
        act = dlg.result; info = self.windows.get(tag)
        if not act or not info: return

        if act=='delete':
            self.canvas.delete(info['id']); del self.windows[tag]

        elif act=='move':
            wid = info['id']
            self.canvas.itemconfigure(wid,dash=(4,2))
            self.selected_window = tag
            self.drag_data = {'x':e.x,'y':e.y}
            self.canvas.unbind('<Button-1>')
            self.canvas.bind('<Motion>', self.move_window)
            self.bind('<Return>',        self.finish_move_window)

        elif act=='resize':
            newlen = simpledialog.askfloat('Resize Window','Length (ft):',
                                           initialvalue=info['length_ft'],parent=self)
            if newlen is None: return
            coords = self.canvas.coords(info['id'])
            mx,my = (coords[0]+coords[2])/2,(coords[1]+coords[3])/2
            self.canvas.delete(info['id'])
            info['length_ft'] = newlen
            self._place_window(info['wall_idx'],mx,my,newlen)

    def move_window(self, e):
        tag = self.selected_window; info=self.windows.get(tag)
        if not info: return
        idx = info['wall_idx']
        x1,y1,x2,y2 = self.canvas.coords(self.wall_lines[idx])
        dx,dy = x2-x1,y2-y1
        t = ((e.x-x1)*dx + (e.y-y1)*dy)/(dx*dx+dy*dy)
        t = max(0,min(1,t))
        midx,midy = x1+dx*t, y1+dy*t
        half = info['length_ft']*BASE_SCALE*self.zoom/2
        ux,uy = dx/math.hypot(dx,dy), dy/math.hypot(dx,dy)
        p1=(midx-ux*half, midy-uy*half); p2=(midx+ux*half, midy+uy*half)
        self.canvas.coords(info['id'],*p1,*p2)

    def finish_move_window(self, e=None):
        tag = self.selected_window
        if tag:
            wid = self.windows[tag]['id']
            self.canvas.itemconfigure(wid, dash=())
        self.canvas.unbind('<Motion>')
        self.unbind('<Return>')
        self.canvas.bind('<Button-1>', self.select_item)
        self.selected_window = None
        self.drag_data = {}

    # --- Furniture ---
    def prepare_furniture(self): #this makes the firnutires
        name = simpledialog.askstring('Furniture','Enter name:',parent=self)
        if not name: return
        dlg  = OptionDialog(self,'Shape','Select shape:',
                            [('rectangle','Rectangle'),('circle','Circle')])
        shape = dlg.result
        if not shape: return
        self.new_item = {'name':name,'shape':shape}
        self.set_mode('add_furn')

    def place_furniture(self, e):
        info = self.new_item
        tag  = f'furn{len(self.furniture)}'
        if info['shape']=='rectangle':
            w = simpledialog.askfloat('Width','Width (ft):',parent=self)
            h = simpledialog.askfloat('Height','Height (ft):',parent=self)
            if None in (w,h):
                self.set_mode('select'); return
            pw,ph = w*BASE_SCALE*self.zoom/2, h*BASE_SCALE*self.zoom/2
            x1,y1=e.x-pw,e.y-ph; x2,y2=e.x+pw,e.y+ph
            rid = self.canvas.create_rectangle(x1,y1,x2,y2,fill='#ddd',tags=(tag,))
            self.furniture[tag] = {'id':rid,'name':info['name'],
                                   'shape':'rect','w':w,'h':h,'angle':0}
        else:
            d = simpledialog.askfloat('Diameter','Diameter (ft):',parent=self)
            if d is None:
                self.set_mode('select'); return
            r = d*BASE_SCALE*self.zoom/2
            oid = self.canvas.create_oval(e.x-r,e.y-r,e.x+r,e.y+r,fill='#ddd',tags=(tag,))
            self.furniture[tag] = {'id':oid,'name':info['name'],
                                   'shape':'circ','d':d,'angle':0}
        self.bind_furniture(tag)
        self.actions.append({'type':'furn','tag':tag})
        self.set_mode('select')

    def bind_furniture(self, tag):
        self.canvas.tag_bind(tag,'<Enter>',      lambda e,t=tag: self.show_tooltip(e,t))
        self.canvas.tag_bind(tag,'<Leave>',      lambda e: self.hide_tooltip())
        # quick drag
        self.canvas.tag_bind(tag,'<ButtonPress-1>',lambda e,t=tag: self.furn_press(e,t))
        self.canvas.tag_bind(tag,'<B1-Motion>',    lambda e,t=tag: self.furn_drag(e,t))

    def show_tooltip(self, e, tag):
        name = self.furniture[tag]['name']
        self.tip = tk.Toplevel(self); self.tip.overrideredirect(True)
        self.tip.geometry(f'+{e.x_root+10}+{e.y_root+10}')
        #tk.Label(self.tip, text=name, bg='yellow', bd=1, relief='solid').pack()
        ttkb.Label(self.tip, text=name, bootstyle='info-inverse').pack()
    def hide_tooltip(self):
        if hasattr(self,'tip'): self.tip.destroy()

    def furn_press(self, e, tag):
        self.selected_item = tag
        self.prev = (e.x,e.y)
        self.orig = self.canvas.coords(self.furniture[tag]['id'])

    def furn_drag(self, e, tag):
        dx,dy = e.x-self.prev[0], e.y-self.prev[1]
        self.canvas.move(tag,dx,dy)
        self.prev = (e.x,e.y)

    def start_furn_move(self, tag, e):
        fid = self.furniture[tag]['id']
        box = self.canvas.bbox(fid)
        self.move_outline = self.canvas.create_rectangle(
            *box, dash=(4,2), fill='', outline='black'
        )
        self.selected_item = tag
        self.drag_data = {'x0':e.x,'y0':e.y,'orig':self.canvas.coords(fid)}
        self.canvas.unbind('<Button-1>')
        self.canvas.bind('<Motion>', self.move_furn)
        self.bind('<Return>',        self.finish_move_furn)

    def move_furn(self, e):
        tag = self.selected_item
        if not tag: return
        self.canvas.bind('<Key>', self.on_key_press) ######################################also here
        self.canvas.focus_set()
        fid = self.furniture[tag]['id']
        dx = e.x - self.drag_data['x0']; dy = e.y - self.drag_data['y0']
        ox1,oy1,ox2,oy2 = self.drag_data['orig']
        new = [ox1+dx,oy1+dy,ox2+dx,oy2+dy]
        self.canvas.coords(fid,*new)
        self.canvas.coords(self.move_outline,*self.canvas.bbox(fid))

        ################################################################################## editing here
    def on_key_press(self, event):
        if event.char.lower() == 'r':
            self.edit_furn_rotate(self.selected_item)
            ##############################################################################

    def finish_move_furn(self, e=None):
        self.canvas.unbind('<Motion>')
        self.unbind('<Return>')
        if self.move_outline:
            self.canvas.delete(self.move_outline)
            self.move_outline = None
        self.canvas.bind('<Button-1>', self.select_item)
        self.selected_item = None
        self.drag_data     = {}

    # --- Rotate Furniture ---
    def edit_furn_rotate(self, tag):
        info = self.furniture.get(tag)
        if not info:
            return
        if info['shape'] == 'circ':
            messagebox.showinfo("Rotate", "Circular furniture doesn't need rotation.")
            return

        initial = info.get('angle', 0)
        dlg = tk.Toplevel(self)
        dlg.transient(self)
        dlg.title("Rotate Furniture")
        angle_var = tk.DoubleVar(value=initial)

        def on_scale(v):
            ang = float(v)
            self.apply_furn_rotation(tag, ang)

        scale = tk.Scale(dlg,
                         label="Angle ⟳",
                         variable=angle_var,
                         from_=0, to=360,
                         orient='horizontal',
                         command=on_scale)
        scale.pack(fill='x', padx=10, pady=10)

        btns = tk.Frame(dlg); btns.pack(pady=5)
        tk.Button(btns, text="OK", command=dlg.destroy).pack()
        dlg.grab_set()
        self.wait_window(dlg)

        info['angle'] = angle_var.get()

    def apply_furn_rotation(self, tag, angle):
        info = self.furniture.get(tag)
        if not info or info['shape'] != 'rect':
            return

        bbox = self.canvas.bbox(info['id'])
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2

        w = info['w'] * BASE_SCALE * self.zoom
        h = info['h'] * BASE_SCALE * self.zoom
        hw, hh = w/2, h/2

        corners = [(-hw, -hh), ( hw, -hh), ( hw,  hh), (-hw,  hh)]
        θ = math.radians(angle)
        cosθ, sinθ = math.cos(θ), math.sin(θ)

        pts = []
        for dx, dy in corners:
            rx = cx + dx * cosθ - dy * sinθ
            ry = cy + dx * sinθ + dy * cosθ
            pts.extend([rx, ry])

        self.canvas.delete(info['id'])
        new_id = self.canvas.create_polygon(
            pts,
            fill='#ddd',
            tags=(tag,)
        )
        info['id'] = new_id
        self.bind_furniture(tag)

    # --- Selection/Edit Entry Point ---
    def select_item(self, e):
        items = self.canvas.find_overlapping(e.x-3,e.y-3,e.x+3,e.y+3)
        if not items: return
        clicked_item = items[-1]  # last item is the topmost
        tags = self.canvas.gettags(clicked_item)

        # Window
        for t in tags:
            if t.startswith('window'):
                return self.edit_window(e, t)

        # Furniture
        for t in tags:
            if t.startswith('furn') and t in self.furniture:
                tag = t
                info = self.furniture[tag]
                dlg = OptionDialog(self,'Furniture','Action:',[
                    ('move','Move'),
                    ('rotate','Rotate'),
                    ('resize','Resize'),
                    ('delete','Delete'),
                ])
                act = dlg.result
                if act=='delete':
                    self.canvas.delete(info['id'])
                    del self.furniture[t]
                elif act=='move':
                    self.start_furn_move(t, e)
                elif act=='rotate':
                    self.edit_furn_rotate(t)
                elif act=='resize':
                    if info['shape']=='rect':
                        w = simpledialog.askfloat('Width','Width (ft):',
                                                  initialvalue=info['w'], parent=self)
                        h = simpledialog.askfloat('Height','Height (ft):',
                                                  initialvalue=info['h'], parent=self)
                        if w and h:
                            info['w'], info['h'] = w, h
                            self.canvas.coords(
                                info['id'],
                                e.x-w*BASE_SCALE*self.zoom/2,
                                e.y-h*BASE_SCALE*self.zoom/2,
                                e.x+w*BASE_SCALE*self.zoom/2,
                                e.y+h*BASE_SCALE*self.zoom/2
                            )
                    else:
                        d = simpledialog.askfloat('Diameter','Diameter (ft):',
                                                  initialvalue=info['d'], parent=self)
                        if d:
                            info['d'] = d
                            r = d*BASE_SCALE*self.zoom/2
                            self.canvas.coords(
                                info['id'],
                                e.x-r, e.y-r,
                                e.x+r, e.y+r
                            )
                return

        # Walls fallback
        for t in tags:
            if t.startswith('wall'):
                try:
                    idx = self.wall_lines.index(clicked_item)
                except ValueError:
                    idx = int(t[4:])


                dlg = OptionDialog(self,'Wall','Action:',[
                    ('move','Move'),('resize','Resize'),('delete','Delete')
                ])
                act = dlg.result
                if act=='move':
                    self.start_wall_move(idx, e)
                elif act=='resize':
                    self.edit_wall(self.wall_lines[idx])
                elif act=='delete':
                    self.delete_wall_by_index(idx)
                return

if __name__ == '__main__':
    RoomPlanner().mainloop()




