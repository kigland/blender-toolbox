import bpy
import os
import urllib.request
import bmesh
from mathutils import Vector

S3_BUCKET = "https://s3.kigland.cn/blender"


class PropsTextOrderId(bpy.types.PropertyGroup):
    user_input_order_id: bpy.props.StringProperty(
        name="Order ID",
        description="For Order ID",
        default="XXXXXXXX"
    )
    text_order_id: bpy.props.StringProperty(
        name="Text Order ID",
        default="XXXXXXXX"
    )


class OpGenOrderIdLabel(bpy.types.Operator):
    bl_idname = "text.gen_order_id_label"
    bl_label = "Gen OrderID Label"

    def execute(self, context):
        scene = context.scene
        text_tool = scene.text_tool

        # Check if the text object exists
        text_obj = bpy.data.objects.get(text_tool.text_order_id)
        if text_obj is None:
            # Create a new text object
            font_curve = bpy.data.curves.new(type='FONT', name='Font Curve')
            text_obj = bpy.data.objects.new(
                text_tool.text_order_id, font_curve)
            context.collection.objects.link(text_obj)

        # Update the text
        text_obj.data.body = f'KIG.LAND\nKIGURUMI\n{text_tool.user_input_order_id}'

        return {'FINISHED'}


def download_file_and_load(url, temp_dir, blend_filename):
    loaded_objects = []
    temp_blend_path = os.path.join(temp_dir, blend_filename)
    try:
        with urllib.request.urlopen(url) as response:
            with open(temp_blend_path, 'wb') as out_file:
                out_file.write(response.read())

        if os.path.exists(temp_blend_path):
            with bpy.data.libraries.load(temp_blend_path, link=False) as (data_from, data_to):
                data_to.objects = [name for name in data_from.objects if name]

            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
                    loaded_objects.append(obj)

            print(f"Downloaded and loaded: {blend_filename}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if os.path.exists(temp_blend_path):
            os.remove(temp_blend_path)

    return loaded_objects


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


def calculate_average_normal(verts):
    normal_sum = Vector((0.0, 0.0, 0.0))
    for i in range(len(verts) - 2):
        for j in range(i + 1, len(verts) - 1):
            for k in range(j + 1, len(verts)):
                v1 = verts[i].co
                v2 = verts[j].co
                v3 = verts[k].co
                normal = (v2 - v1).cross(v3 - v1)
                normal_sum += normal.normalized()
    return normal_sum.normalized()


def get_selected_face_center_and_normal():
    obj = bpy.context.edit_object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    selected_faces = [f for f in bm.faces if f.select]
    if selected_faces:
        face = selected_faces[0]
        face_normal = face.normal
        face_center = face.calc_center_median()
        world_center = obj.matrix_world @ face_center
        world_normal = obj.matrix_world.to_3x3() @ face_normal.normalized()
        return world_center, world_normal
    else:
        return None, None


class OpGenLogoAndMoveToSelectedVerteces(bpy.types.Operator):
    bl_idname = "object.gen_kigland_logo_and_move_to_selected_vertex"
    bl_label = "Gen Logo"

    def execute(self, context):
        loaded_objects = download_file_and_load(
            f"{S3_BUCKET}/logo.blend",
            bpy.app.tempdir,
            "logo.blend"
        )

        world_center, world_normal = get_selected_face_center_and_normal()

        bpy.ops.object.mode_set(mode='OBJECT')
        for loaded_obj in loaded_objects:
            loaded_obj.location = world_center
            align_quat = Vector((0, 0, 1)).rotation_difference(world_normal)
            loaded_obj.rotation_euler = align_quat.to_euler()
        bpy.ops.object.mode_set(mode='EDIT')

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
    bl_label = "Ave Loc of Act Verts"

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

        row = layout.row()
        row.label(text="OrderId Part", icon='INFO')

        row = layout.row()
        row.prop(context.scene.text_tool, "user_input_order_id")

        row = layout.row()
        row.operator(OpGenOrderIdLabel.bl_idname)

        # if in edit mode, show the active vertex location
        if bpy.context.mode == 'EDIT_MESH':

            obj = bpy.context.edit_object
            me = obj.data
            bm = bmesh.from_edit_mesh(me)

            selected_faces = [f for f in bm.faces if f.select]
            selected_verts = [v for v in bm.verts if v.select]

            if len(selected_verts) > 1:
                row = layout.row()
                row.label(text="On Selected multiple vertices", icon='INFO')

                row = layout.row()
                row.operator(OpShowAverageLocationOfSelectedVerts.bl_idname)

                if len(selected_faces) > 0:

                    row = layout.row()
                    row.label(text="On Selected Face", icon='INFO')

                    row = layout.row()
                    row.operator(OpGenLogoAndMoveToSelectedVerteces.bl_idname)

            if len(selected_verts) == 1:
                row = layout.row()
                row.label(text="On Selected single vertex", icon='INFO')

                row = layout.row()
                row.operator(OpShowActiveVertexLocation.bl_idname)


def register():
    # props
    bpy.utils.register_class(PropsTextOrderId)
    bpy.types.Scene.text_tool = bpy.props.PointerProperty(
        type=PropsTextOrderId)

    # operators
    bpy.utils.register_class(OpGenLogo)
    bpy.utils.register_class(OpGenLockComponents)
    bpy.utils.register_class(OpShowActiveVertexLocation)
    bpy.utils.register_class(OpShowAverageLocationOfSelectedVerts)
    bpy.utils.register_class(OpGenLogoAndMoveToSelectedVerteces)
    bpy.utils.register_class(OpGenOrderIdLabel)

    # panels
    bpy.utils.register_class(UIGenLogo)


def unregister():
    # panels
    bpy.utils.unregister_class(UIGenLogo)

    # operators
    bpy.utils.unregister_class(OpGenLockComponents)
    bpy.utils.unregister_class(OpShowActiveVertexLocation)
    bpy.utils.unregister_class(OpShowAverageLocationOfSelectedVerts)
    bpy.utils.unregister_class(OpGenLogo)
    bpy.utils.unregister_class(OpGenLogoAndMoveToSelectedVerteces)

    bpy.utils.unregister_class(PropsTextOrderId)
    bpy.utils.unregister_class(OpGenOrderIdLabel)

    # props
    del bpy.types.Scene.text_tool


if __name__ == "__main__":
    register()
    # unregister()
