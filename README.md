🏠 RoomForge2D - Version 1.1
RoomForge2D is a graphical room planning tool built using Python and Tkinter, enhanced with the ttkbootstrap UI library. It allows users to design, draw, and modify 2D floor plans with support for walls, windows, and furniture placement — all in an interactive and user-friendly environment.



🔧 Features
Draw rooms with wall segments (snap to straight lines using Shift)

Add, move, resize, and delete windows

Add and manipulate furniture (rectangle or circular shapes)

Zoom in/out for precision

Undo or clear all room objects

Select and edit existing components

Rotate rectangular furniture objects

Smooth drag-and-drop support



📦 Requirements
Before running this program, ensure you have the following installed:

✅ Python Version:
Python 3.7 or newer

✅ Required Packages:
Install the following packages via pip:
  pip install ttkbootstrap
  
Note: Tkinter is included by default with most Python installations.



🚀 How to Run
Download or clone this repository.
Ensure dependencies are installed.
Run the script:
      python room_planner.py
      
On launch, a welcome message will appear. You can then start designing your room.



🕹️ Controls & Usage Tips
🖱 Left-click to draw or place items depending on the selected mode.

🖱 Middle-click & drag to pan across the canvas.

🔍 Use Zoom In and Zoom Out for better visibility.

⌨️ Press Enter to finalize placement of windows/furniture.

🔄 Press R while moving furniture to rotate it.

↩️ Press Ctrl+Z to undo last action.

❌ Press Escape to cancel drawing mode.



🧠 Skills Required to Build This
To develop RoomForge2D, the following technical skills were required:

GUI Design & Event Handling

  Tkinter framework

  Custom dialogs and canvas interaction

Mouse & Keyboard Input Binding

  Handling complex events and modifiers (e.g., Shift, Return)

2D Geometry & Math

  Wall alignment, vector rotation, object positioning

State Management

  Object tracking (walls, windows, furniture), undo/redo stack

Object-Oriented Programming

  Class-based structure (RoomPlanner, OptionDialog)

User Experience Design

  Intuitive tool modes, feedback dialogs, and interactive editing















