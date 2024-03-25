import bpy
import os
import urllib.request
import bmesh
from mathutils import Vector

S3_BUCKET = "https://s3.kigland.cn/blender"


def download_file_and_load(url, temp_dir, blend_filename):
    # This function contains side effects,
    # it downloads a file from a URL and loads it into the current scene
    temp_blend_path = os.path.join(temp_dir, blend_filename)
    try:
        with urllib.request.urlopen(url) as response:
            with open(temp_blend_path, 'wb') as out_file:
                out_file.write(response.read())

        if os.path.exists(temp_blend_path):
            with bpy.data.libraries.load(temp_blend_path, link=False) as (data_from, data_to):
                # Filter out any None objects
                data_to.objects = [name for name in data_from.objects if name]

            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)

            print(f"Downloaded and loaded: {blend_filename}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if os.path.exists(temp_blend_path):
            os.remove(temp_blend_path)


class OpGenLogo(bpy.types.Operator):
    bl_idname = "object.gen_kigland_logo"
    bl_label = "Gen Logo"

    def execute(self, context):
        download_file_and_load(
            f"{S3_BUCKET}/logo.blend",
            bpy.app.tempdir,
            "logo.blend"
        )
        return {'FINISHED'}


class OpGenLockComponents(bpy.types.Operator):
    bl_idname = "object.gen_lock_components"
    bl_label = "Gen NRH Lock "

    def execute(self, context):
        download_file_and_load(
            f"{S3_BUCKET}/lock_nrh.blend",
            bpy.app.tempdir,
            "lock_nrh.blend"
        )
        return {'FINISHED'}


def get_active_vertex_location():
    obj = bpy.context.edit_object
    if obj is None:
        return None

    bm = bmesh.from_edit_mesh(obj.data)

    active_vert = bm.select_history.active

    if isinstance(active_vert, bmesh.types.BMVert) and active_vert.select:
        # Apply the object's world matrix to the active vertex's coordinate
        return obj.matrix_world @ active_vert.co
    else:
        return None


def get_average_location_of_selected_verts():
    obj = bpy.context.edit_object
    if obj is None:
        return None

    bm = bmesh.from_edit_mesh(obj.data)
    selected_verts = [v for v in bm.verts if v.select]

    if not selected_verts:
        return None

    # Initialize a zero vector for accumulating vertex coordinates
    avg_co = Vector((0.0, 0.0, 0.0))

    # Sum the coordinates of all selected vertices
    for vert in selected_verts:
        avg_co += obj.matrix_world @ vert.co

    # Divide by the number of selected vertices to get the average
    avg_co /= len(selected_verts)

    return avg_co


class OpShowActiveVertexLocation(bpy.types.Operator):
    bl_idname = "object.show_active_vertex_location"
    bl_label = "Vertex Location"

    def execute(self, context):
        loc = get_active_vertex_location()
        if loc is not None:
            self.report({'INFO'}, f"Active vertex location: {loc}")
        else:
            self.report(
                {'ERROR'}, "No active vertex selected or selected over single vertex")
        return {'FINISHED'}


class OpShowAverageLocationOfSelectedVerts(bpy.types.Operator):
    bl_idname = "object.show_average_location_of_selected_verts"
    bl_label = "Average Location of Selected Verts"

    def execute(self, context):
        loc = get_average_location_of_selected_verts()
        if loc is not None:
            self.report({'INFO'}, f"Average location of selected verts: {loc}")
        else:
            self.report({'ERROR'}, "No selected verts")
        return {'FINISHED'}


class UIGenLogo(bpy.types.Panel):
    bl_label = "KigLand Toolbox"
    bl_idname = "OBJECT_PT_kigland_toolbox"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text="Components", icon='INFO')

        row = layout.row()
        row.operator(OpGenLogo.bl_idname)

        row = layout.row()
        row.operator(OpGenLockComponents.bl_idname)

        # if in edit mode, show the active vertex location
        if bpy.context.mode == 'EDIT_MESH':
            row = layout.row()
            row.operator(OpShowActiveVertexLocation.bl_idname)

            row = layout.row()
            row.operator(OpShowAverageLocationOfSelectedVerts.bl_idname)


def register():
    bpy.utils.register_class(OpGenLogo)
    bpy.utils.register_class(OpGenLockComponents)
    bpy.utils.register_class(OpShowActiveVertexLocation)
    bpy.utils.register_class(OpShowAverageLocationOfSelectedVerts)
    bpy.utils.register_class(UIGenLogo)


def unregister():
    bpy.utils.unregister_class(UIGenLogo)
    bpy.utils.unregister_class(OpGenLockComponents)
    bpy.utils.unregister_class(OpShowActiveVertexLocation)
    bpy.utils.unregister_class(OpShowAverageLocationOfSelectedVerts)
    bpy.utils.unregister_class(OpGenLogo)


if __name__ == "__main__":
    register()
    # unregister()
