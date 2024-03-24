import bpy
import os
import urllib.request


class OpGenLogo(bpy.types.Operator):
    bl_idname = "object.gen_kigland_logo"
    bl_label = "Gen Logo"

    def execute(self, context):
        url = "https://s3.kigland.cn/blender/logo.blend"
        temp_dir = bpy.app.tempdir
        blend_filename = "logo.blend"
        temp_blend_path = os.path.join(temp_dir, blend_filename)

        try:
            with urllib.request.urlopen(url) as response:
                with open(temp_blend_path, 'wb') as out_file:
                    out_file.write(response.read())
            with bpy.data.libraries.load(temp_blend_path, link=False) as (data_from, data_to):
                data_to.objects = [name for name in data_from.objects]
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
                    self.report({'INFO'}, f"Downloaded and loaded: {blend_filename}")
                    os.remove(temp_blend_path)

        except Exception as e:
            self.report({'ERROR'}, str(e))

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
        row.operator(OpGenLogo.bl_idname)


def register():
    bpy.utils.register_class(OpGenLogo)
    bpy.utils.register_class(UIGenLogo)


def unregister():
    bpy.utils.unregister_class(UIGenLogo)
    bpy.utils.unregister_class(OpGenLogo)


if __name__ == "__main__":
    register()
    unregister()
