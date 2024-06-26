import bpy
import inspect
import os
import urllib.request
import bmesh
from mathutils import Vector
import ssl
import sys


S3_BUCKET = "https://s3.kigland.cn/blender"


def clean_float(value: float, precision: int = 0) -> str:
    # Avoid scientific notation and strip trailing zeros: 0.000 -> 0.0

    text = f"{value:.{precision}f}"
    index = text.rfind(".")

    if index != -1:
        index += 2
        head, tail = text[:index], text[index:]
        tail = tail.rstrip("0")
        text = head + tail

    return text


def get_unit(unit_system: str, unit: str) -> tuple[float, str]:
    # Returns unit length relative to meter and unit symbol

    units = {
        "METRIC": {
            "KILOMETERS": (1000.0, "km"),
            "METERS": (1.0, "m"),
            "CENTIMETERS": (0.01, "cm"),
            "MILLIMETERS": (0.001, "mm"),
            "MICROMETERS": (0.000001, "µm"),
        },
        "IMPERIAL": {
            "MILES": (1609.344, "mi"),
            "FEET": (0.3048, "\'"),
            "INCHES": (0.0254, "\""),
            "THOU": (0.0000254, "thou"),
        },
    }

    try:
        return units[unit_system][unit]
    except KeyError:
        fallback_unit = "CENTIMETERS" if unit_system == "METRIC" else "INCHES"
        return units[unit_system][fallback_unit]

class PropsTextOrderId(bpy.types.PropertyGroup):
    user_input_order_id: bpy.props.StringProperty(
        name="Order ID",
        description="For Order ID",
        default="AXX-ORDERID"
    )
    text_order_id: bpy.props.StringProperty(
        name="Text Order ID",
        default="AXX-ORDERID"
    )
    gen_full_order_id_label: bpy.props.BoolProperty(
        name="Gen Full Order ID Label",
        default=False
    )


def poll_mesh_object(self, object):
    return object.type == 'MESH'


class PropsRealHeadSizes(bpy.types.PropertyGroup):

    kigurumi_type: bpy.props.EnumProperty(
        name="Product",
        items=[
            ('TYPE_G', "TYPE_G", "Kig.land product TYPE_G"),
            ('TYPE_A', "TYPE_A", "Kig.land product TYPE_A"),
        ]
    )

    kigurumi_object_type_g_fe: bpy.props.PointerProperty(
        name="FE Object",
        type=bpy.types.Object,
        poll=poll_mesh_object
    )

    kigurumi_object_type_g_be: bpy.props.PointerProperty(
        name="BE Object",
        type=bpy.types.Object,
        poll=poll_mesh_object
    )

    kigurumi_object_type_a: bpy.props.PointerProperty(
        name="Object",
        type=bpy.types.Object,
        poll=poll_mesh_object
    )

    head_height: bpy.props.FloatProperty(
        name="Head Height",
        default=240.0
    )

    head_width: bpy.props.FloatProperty(
        name="Head Width",
        default=180.0
    )

    head_circumference: bpy.props.FloatProperty(
        name="Head Circumference",
        default=580.0
    )

    head_type_items = [('A{}'.format(i),
                        "GB/T Std A{}".format(i), "Description A{}".format(i)) for i in range(2, 9)]
    head_type: bpy.props.EnumProperty(
        name="GB Head",
        items=head_type_items
    )

    head_gen_scale_by: bpy.props.EnumProperty(
        name="Scale By",
        items=[
            ('SCALE_BY_HEIGHT', "Head Height", "Scale head by real head height"),
            ('SCALE_BY_WIDTH', "Head Width", "Scale head by real head width"),
        ]
    )

    body_height: bpy.props.FloatProperty(
        name="Body Height",
        default=1680.0
    )

    shoulder_width: bpy.props.FloatProperty(
        name="Shoulder Width",
        default=390.0
    )

    eyes_height: bpy.props.FloatProperty(
        name="Eyes Height",
        default=120.0
    )

    # NOTE: Bi-pupillary distance
    eyes_spacing: bpy.props.FloatProperty(
        name="Eyes Spacing",
        default=70.0
    )
    padding_fill_thickness: bpy.props.FloatProperty(
        name="Padding thickness",
        default=35.0
    )

class CostMonitor(bpy.types.PropertyGroup):
    # unit 1.34 g/cm^3
    density: bpy.props.FloatProperty(
        name="Density",
        default=1.13
    )

    material_cost: bpy.props.FloatProperty(
        name="Material Cost",
        default=0.35
    )

    selected_object_info:  bpy.props.StringProperty(
        name="Selected Object Info",
        default="No Object Selected"
    )

    volume: bpy.props.StringProperty(
        name="Volume",
        default="0.0"
    )

    cost: bpy.props.StringProperty(
        name="Cost",
        default="0.0 CNY"
    )
    weight: bpy.props.StringProperty (
        name="Weight",
        default="0 g"
    )    


def download_file_and_load(url, temp_dir, blend_filename):
    loaded_objects = []
    temp_blend_path = os.path.join(temp_dir, blend_filename)

    # NOTE: WARNING it will not verify cert
    context = ssl._create_unverified_context()

    with urllib.request.urlopen(url, context=context) as response:
        with open(temp_blend_path, 'wb') as out_file:
            out_file.write(response.read())

    if os.path.exists(temp_blend_path):
        with bpy.data.libraries.load(temp_blend_path, link=False) as (data_from, data_to):
            data_to.objects = [name for name in data_from.objects if name]

        for obj in data_to.objects:
            if obj is not None:
                bpy.context.collection.objects.link(obj)
                loaded_objects.append(obj)

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


class OpInitEnvUnitSettings(bpy.types.Operator):
    bl_idname = "object.init_env_units"
    bl_label = "Init Env Units"

    def execute(self, context):

        scene = bpy.context.scene
        unit_settings = scene.unit_settings
        unit_settings.system = 'METRIC'
        unit_settings.scale_length = 0.001
        unit_settings.length_unit = 'MILLIMETERS'
        unit_settings.mass_unit = 'KILOGRAMS'
        unit_settings.time_unit = 'SECONDS'

        return {'FINISHED'}


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


class OpGenGBTHead(bpy.types.Operator):
    bl_idname = "object.gen_gbt_head"
    bl_label = "Gen GB/T Head Model"

    def execute(self, context):
        current_head = download_file_and_load(
            f"{S3_BUCKET}/ref_head_a2.blend",
            bpy.app.tempdir,
            "ref_head_a2.blend"
        )

        head_data = context.scene.head_data
        scale_property = 'head_height' if head_data.head_gen_scale_by == 'SCALE_BY_HEIGHT' else 'head_width'
        scale_target = getattr(head_data, scale_property)
        scale_factor = scale_target / current_head[0].dimensions.z

        current_head[0].scale *= scale_factor

        return {'FINISHED'}


class OpGenEyesHole(bpy.types.Operator):
    bl_idname = "object.gen_eyes_hole"
    bl_label = "Gen Eyes Hole"

    def execute(self, context):
        eye_hole = download_file_and_load(
            f"{S3_BUCKET}/eye_hole.blend",
            bpy.app.tempdir,
            "eye_hole.blend"
        )
        head_data = context.scene.head_data
        eye_spacing = head_data.eyes_spacing

        eye_hole[0].location = (eye_spacing / 2, eye_hole[0].location.y, eye_hole[0].location.z)
        
        bpy.context.view_layer.objects.active = eye_hole[0]
        bpy.ops.object.transform_apply(location=True)
        
        mirror_modifier = eye_hole[0].modifiers.new(name="Mirror", type='MIRROR')
        mirror_modifier.use_axis[0] = True
        
        return {'FINISHED'}


class OpGenEars(bpy.types.Operator):
    bl_idname = "object.gen_kigland_ears"
    bl_label = "Gen Ears"

    def execute(self, context):
        download_file_and_load(
            f"{S3_BUCKET}/ears.blend",
            bpy.app.tempdir,
            "ears.blend"
        )
        return {'FINISHED'}


class OpRemoveObjectAllVertexGroups(bpy.types.Operator):
    bl_idname = "object.rm_mesh_vertex_groups"
    bl_label = "Remove All Vertex Groups"

    def execute(self, context):
        obj = bpy.context.active_object
        if obj and obj.type == 'MESH':
            obj.vertex_groups.clear()
        return {'FINISHED'}


class OpRemoveObjectAllShapeKeys(bpy.types.Operator):
    bl_idname = "object.rm_mesh_shape_keys"
    bl_label = "Remove All shape keys"

    def execute(self, context):
        obj = bpy.context.active_object
        if obj and obj.type == 'MESH' and obj.data.shape_keys:
            shape_key_data = obj.data.shape_keys
            key_blocks = shape_key_data.key_blocks
            for key_block in key_blocks:
                obj.shape_key_remove(key_block)
        return {'FINISHED'}


class OpApplyShapekeys(bpy.types.Operator):
    bl_idname = "object.apply_shape_keys"
    bl_label = "Apply Shape Keys"

    def execute(self, context):
        obj = bpy.context.active_object
        if obj and obj.type == 'MESH' and obj.data.shape_keys:
            shape_key_data = obj.data.shape_keys
            key_blocks = shape_key_data.key_blocks
            active_shape_key_index = obj.active_shape_key_index

            bpy.ops.object.shape_key_add(from_mix=True)
            obj.active_shape_key_index = len(key_blocks)

            for i, key_block in reversed(list(enumerate(key_blocks))):
                if i != active_shape_key_index:
                    obj.active_shape_key_index = i
                    bpy.ops.object.shape_key_remove(all=False)
            for key_block in key_blocks:
                obj.shape_key_remove(key_block)
            self.report({'INFO'}, "Okay, you're free to use the modifier.")

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


class OpGenOrderIdLabel(bpy.types.Operator):
    bl_idname = "text.gen_order_id_label"
    bl_label = "Gen OrderID Label"

    def execute(self, context):
        scene = context.scene
        text_tool = scene.text_tool

        # Create a new text object
        font_curve = bpy.data.curves.new(type='FONT', name='Font Curve')
        text_obj = bpy.data.objects.new(
            "label.order", font_curve)
        context.collection.objects.link(text_obj)

        if text_tool.gen_full_order_id_label:
            text_obj.data.body = f'KIG.LAND\nKIGURUMI\n{text_tool.user_input_order_id}'
        else:
            text_obj.data.body = f'{text_tool.user_input_order_id}'

        # Update the scene to calculate dimensions
        bpy.context.view_layer.update()

        # Resize the text object to have a width of 1.5
        text_height = text_obj.dimensions.y
        target_height = 0

        if text_tool.gen_full_order_id_label:
            target_height = 10
        else:
            target_height = 3

        scale_factor = target_height / text_height
        text_obj.scale = (scale_factor, scale_factor, scale_factor)

        world_center = world_normal = None

        try:
            (world_center, world_normal) = get_selected_face_center_and_normal()
            bpy.ops.object.mode_set(mode='OBJECT')
            pass
        except:  # noqa: E722
            self.report(
                {'INFO'}, "If your need move it, plz use it in editor mode")

        # Clean active object
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)

        text_obj.select_set(True)
        context.view_layer.objects.active = text_obj
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.extrude_region_move(  # extrude_amount
            TRANSFORM_OT_translate={"value": (0, 0, 2)})
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.transform_apply(
            location=False, rotation=False, scale=True)

        if world_center is None:
            return {'FINISHED'}
        else:
            text_obj.location = world_center
            align_quat = Vector((0, 0, 1)).rotation_difference(world_normal)
            text_obj.rotation_euler = align_quat.to_euler()
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


# OpApplyShapekeys
def row_op(self, op_class):
    self.layout.row().operator(op_class.bl_idname)


def row_label(self, text, icon=None):
    self.layout.row().label(text=text, **({'icon': icon} if icon else {}))


def row_prop(self, context, id):
    self.layout.row().prop(context, id)


class UIEnv(bpy.types.Panel):
    bl_label = "KigLand - Env Unit"
    bl_idname = "OBJECT_PT_kigland_toolbox_env"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        row_label(self, "Env init", "OPTIONS")
        row_op(self, OpInitEnvUnitSettings)


class UIInfoState(bpy.types.Panel):
    bl_label = "KigLand - Info State"
    bl_idname = "OBJECT_PT_kigland_toolbox_info"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        if bpy.context.mode == 'EDIT_MESH':

            obj = bpy.context.edit_object
            me = obj.data
            bm = bmesh.from_edit_mesh(me)

            selected_faces = [f for f in bm.faces if f.select]
            selected_verts = [v for v in bm.verts if v.select]

            if len(selected_verts) > 1:
                row_label(self, "Vertex info", "PIVOT_CURSOR")

                if (loc := get_average_location_of_selected_verts()):
                    row_label(self, f"Ave. loc: X:{loc.x:.2f}, Y:{loc.y:.2f}, Z:{loc.z:.2f}")

                # row_op(self,OpShowAverageLocationOfSelectedVerts)

                if len(selected_faces) > 0:
                    pass

            if len(selected_verts) == 1:
                row_label(self, "Vertex info", "PIVOT_CURSOR")
                loc = get_active_vertex_location()
                row_label(self, f"loc: X:{loc.x:.2f}, Y:{loc.y:.2f}, Z:{loc.z:.2f}")


class UIToolBox(bpy.types.Panel):
    bl_label = "KigLand - Components"
    bl_idname = "OBJECT_PT_kigland_toolbox"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        row_op(self, OpGenLogo)
        row_op(self, OpGenEars)
        row_op(self, OpGenLockComponents)

        layout.separator()
        layout.separator()

        # Order ID
        row_label(self, "Order Labels & Order Id", "LINENUMBERS_ON")
        row_prop(self, context.scene.text_tool, "user_input_order_id")
        row_prop(self, context.scene.text_tool, "gen_full_order_id_label")
        row_op(self, OpGenOrderIdLabel)

        # if in edit mode, show the active vertex location
        if bpy.context.mode == 'EDIT_MESH':

            obj = bpy.context.edit_object
            me = obj.data
            bm = bmesh.from_edit_mesh(me)

            selected_faces = [f for f in bm.faces if f.select]
            selected_verts = [v for v in bm.verts if v.select]

            if len(selected_verts) > 1:
                #
                if len(selected_faces) > 0:
                    row_label(self, "On Selected Face", "FACE_MAPS")
                    row_op(self, OpGenLogoAndMoveToSelectedVerteces)
                    row_op(self, OpGenOrderIdLabel)

            if len(selected_verts) == 1:
                pass


class UIBodyData(bpy.types.Panel):
    bl_label = "KigLand - Body & Head"
    bl_idname = "OBJECT_PT_kigland_toolbox_body_and_head"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        head_data = context.scene.head_data
        """
        row_prop(self, head_data, "kigurumi_type")

        if head_data.kigurumi_type == "TYPE_G":
            # row_label(self,"All generator, need selected Object")
            row_prop(self, head_data, "kigurumi_object_type_g_fe")
            row_prop(self, head_data, "kigurumi_object_type_g_be")

            if (head_data.kigurumi_object_type_g_fe is None) or \
                    (head_data.kigurumi_object_type_g_be is None):
                row_label(self, "Need select Kigurumi Object",
                          "SEQUENCE_COLOR_01")
            else:
                row_label(
                    self, "Object Selected, plz make sure correct", "SEQUENCE_COLOR_04")

        if head_data.kigurumi_type == "TYPE_A":

            row_prop(self, head_data, "kigurumi_object_type_a")
            if (head_data.kigurumi_object_type_a is None):
                row_label(self, "Need select Kigurumi Object",
                          "SEQUENCE_COLOR_01")
            else:
                row_label(
                    self, "Object Selected, plz make sure correct", "SEQUENCE_COLOR_04")
        """
        # GB/T HEAD GENERATOR
        row_label(self, "Head (mm)", "COMMUNITY")
        row_prop(self, head_data, "head_height")
        row_prop(self, head_data, "head_width")
        #row_prop(self, head_data, "head_circumference")

        if (head_data.head_width < head_data.head_height < head_data.head_circumference) and\
                head_data.head_width >= 120 and \
                head_data.head_height >= 150 and \
                head_data.head_circumference >= 500 and \
                head_data.head_circumference <= 650:
            row_label(self, "DATA CORRECT", "SEQUENCE_COLOR_04")
        else:
            row_label(self, "WARNING DATA MAYBE INCORRECT",
                      "SEQUENCE_COLOR_01")

        row_prop(self, head_data, "head_gen_scale_by")
        # row_prop(self,head_data, "head_type")

        row_op(self, OpGenGBTHead)
        
        # about eye spacing
        row_label(self, "Eyes (mm)", "BLENDER")

        
        # row_prop(self, head_data, "eyes_height")
        row_prop(self, head_data, "eyes_spacing")
        if head_data.eyes_spacing < head_data.head_width * 0.75 and\
            head_data.eyes_spacing > head_data.head_width * 0.1:
            row_label(self, "EYES SPACING CORRECT", "SEQUENCE_COLOR_04")
        else:
            row_label(self, "WARNING DATA MAYBE INCORRECT",
                      "SEQUENCE_COLOR_01")
            
        row_op(self, OpGenEyesHole)

        row_label(self, "Body (mm)", "MATCLOTH")
        row_prop(self, head_data, "body_height")
        row_prop(self, head_data, "shoulder_width")

        if head_data.shoulder_width < 550 and \
            head_data.shoulder_width > 320:
            row_label(self, "SHOULDER CORRECT", "SEQUENCE_COLOR_04")
        else:
            row_label(self, "WARNING DATA MAYBE INCORRECT",
                      "SEQUENCE_COLOR_01")
        
        # Suggestion Part
        row_label(self, "Suggestion Kigurumi Props", "INFO")

        kig_width_low = (head_data.shoulder_width*0.53)
        kig_width_max = (head_data.shoulder_width*0.57)
        row_label(self, f"Width:  {kig_width_low:.2f} - {kig_width_max:.2f} mm")
        row_label(
            self, f"Height (1/5.5): {head_data.body_height * (1/5.5):.2f} mm")
        row_label(
            self, f"Height (1/6.0): {head_data.body_height * (1/6.0):.2f} mm")
        row_label(
            self, f"Height (1/6.5): {head_data.body_height * (1/6.5):.2f} mm")
        row_label(
            self, f"Height (1/7.0): {head_data.body_height * (1/7.0):.2f} mm")
        
        # Calc 
        
        selected_objects = context.selected_objects
        if not selected_objects:
            layout.label(text="No objects selected.")
            return

        # Calculate the total bounding box
        min_x, min_y, min_z = [float('inf')] * 3
        max_x, max_y, max_z = [float('-inf')] * 3

        for obj in selected_objects:
            # We need to calculate the global position of the bounding box corners
            for corner in obj.bound_box:
                global_corner = obj.matrix_world @ Vector(corner)
                min_x = min(min_x, global_corner.x)
                min_y = min(min_y, global_corner.y)
                min_z = min(min_z, global_corner.z)
                max_x = max(max_x, global_corner.x)
                max_y = max(max_y, global_corner.y)
                max_z = max(max_z, global_corner.z)

        total_width = max_x - min_x
        total_depth = max_y - min_y
        total_height = max_z - min_z

        # Display the total bounding box dimensions
        box = layout.box()
        col = box.column()
        
        if total_width > kig_width_low and total_width < kig_width_max:
            col.label(text=f"Width(X): {total_width:.2f} mm",icon='SEQUENCE_COLOR_04')
        else:
            col.label(text=f"Width(X): {total_width:.2f} mm",icon='SEQUENCE_COLOR_01')
        col.label(text=f"Depth(Y): {total_depth:.2f} mm",icon='SEQUENCE_COLOR_09')
        
        kigurumi_height_min = head_data.body_height * (1/6.5)
        kigurumi_height_max = head_data.body_height * (1/5.5)
        
        if total_height > kigurumi_height_min and total_height < kigurumi_height_max:
            col.label(text=f"Height(Z): {total_height:.2f} mm",icon='SEQUENCE_COLOR_04')
        else:
            col.label(text=f"Height(Z): {total_height:.2f} mm",icon='SEQUENCE_COLOR_01')
        
            
        # TODO: for calc the eyes hole positions
        #row_label(self, "Misc (mm)", "OUTLINER_OB_CURVES")
        #row_prop(self, head_data, "padding_fill_thickness")


class UIDangerOp(bpy.types.Panel):
    bl_label = "KigLand - Danger Op"
    bl_idname = "OBJECT_PT_kigland_danger_op"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Dangerous
        row_label(self, "Before apply Modifier", "ERROR")
        row_op(self, OpRemoveObjectAllVertexGroups)
        row_op(self, OpRemoveObjectAllShapeKeys)
        row_op(self, OpApplyShapekeys)

def bmesh_copy_from_object(obj, transform=True, triangulate=True, apply_modifiers=False):
    """Returns a transformed, triangulated copy of the mesh"""

    assert obj.type == 'MESH'

    if apply_modifiers and obj.modifiers:
        import bpy
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        me = obj_eval.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        obj_eval.to_mesh_clear()
    else:
        me = obj.data
        if obj.mode == 'EDIT':
            bm_orig = bmesh.from_edit_mesh(me)
            bm = bm_orig.copy()
        else:
            bm = bmesh.new()
            bm.from_mesh(me)

    # TODO. remove all customdata layers.
    # would save ram

    if transform:
        matrix = obj.matrix_world.copy()
        if not matrix.is_identity:
            bm.transform(matrix)
            # Update normals if the matrix has no rotation.
            matrix.translation.zero()
            if not matrix.is_identity:
                bm.normal_update()

    if triangulate:
        bmesh.ops.triangulate(bm, faces=bm.faces)

    return bm

class OpGenCost(bpy.types.Operator):
    bl_idname = "object.gen_cost"
    bl_label = "Gen Cost"

    def execute(self, context):
        
        cost_monitor = context.scene.cost_monitor
        
        scene = context.scene
        unit = scene.unit_settings
        scale = 1.0 if unit.system == 'NONE' else unit.scale_length
        obj = context.active_object

        bm = bmesh_copy_from_object(obj, apply_modifiers=True)
        volume = bm.calc_volume()
        bm.free()
        volume_fmt = ""
        if unit.system == 'NONE':
            volume_fmt = clean_float(volume, 8)
        else:
            length, symbol = get_unit(unit.system, unit.length_unit)
            volume_unit = volume * (scale ** 3.0) / (length ** 3.0)
            

            volume_str = clean_float(volume_unit, 4)
            volume_fmt = f"{volume_str} {symbol}³"

            volume_cm3 = volume * (scale ** 3.0) / (0.01 ** 3.0)
            weight = volume_cm3 * cost_monitor.density
            weight_fmt = clean_float(weight,2)
            weight_str = f"{weight_fmt} g"
            cost = volume_cm3 * cost_monitor.density * cost_monitor.material_cost
            cost_fmt = clean_float(cost, 2)
            cost_str = f"{cost_fmt} CNY"
            
            cost_monitor.selected_object_info = f"{volume_fmt} -> {cost_str}"
            cost_monitor.volume = volume_fmt
            cost_monitor.cost = cost_str
            cost_monitor.weight = weight_str
        return {'FINISHED'}

class UICosts(bpy.types.Panel):
    bl_label = "KigLand - Costs Monitor"
    bl_idname = "OBJECT_PT_kigland_costs_op"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'KigLand Toolbox'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        cost_monitor = context.scene.cost_monitor

        row_label(self, "Material Costs", "MATERIAL")
        row_prop(self, cost_monitor, "density")
        row_prop(self, cost_monitor, "material_cost")
        
        row_label(self, "Total Costs", "RNA")
        row_prop(self, cost_monitor, "volume")
        row_prop(self, cost_monitor, "cost")
        row_prop(self, cost_monitor, "weight")
        row_op(self, OpGenCost)
        row_label(self, "Base Price (Supports Excluded)")

            
blender_classes = (
    bpy.types.Operator,
    bpy.types.Panel,
    bpy.types.PropertyGroup
)


def auto_register_unregister_classes(classes_to_check, register=True):
    cls_members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
    for name, cls in cls_members:
        if any(issubclass(cls, blender_class) for blender_class in classes_to_check):
            if register:
                bpy.utils.register_class(cls)
            else:
                bpy.utils.unregister_class(cls)


def register():

    # OP, UI
    auto_register_unregister_classes(blender_classes, register=True)

    # props
    bpy.types.Scene.head_data = bpy.props.PointerProperty(
        type=PropsRealHeadSizes)
    bpy.types.Scene.text_tool = bpy.props.PointerProperty(
        type=PropsTextOrderId)
    bpy.types.Scene.cost_monitor = bpy.props.PointerProperty(
        type=CostMonitor)


def unregister():
    # OP, UI
    auto_register_unregister_classes(blender_classes, register=False)

    # props
    del bpy.types.Scene.text_tool
    del bpy.types.Scene.head_data
    del bpy.types.Scene.cost_monitor


# addon_name = __name__.partition('.')[0]

# if __name__ == "__main__":

#     # in scripting mode

#     register()

#     if addon_name in sys.modules:
#         unregister()

#     register()

#     # unregister()