from . import scripting

bl_info = {
    "name": "Kigland Toolbox",
    "blender": (4, 0, 0),
    "category": "View3D",
    "author": "Kig.Land",
    "version": (0, 1, 0),
    "location": "3D Viewport > Object",
    "description": "Tool box for kigland workshop",
    "warning": "",
    "doc_url": "https://github.com/kigland/blender-toolbox",
}

# blender register
def register():
    scripting.register()

def unregister():
    scripting.unregister()