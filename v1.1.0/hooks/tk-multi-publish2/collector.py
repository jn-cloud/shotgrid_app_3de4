# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import mimetypes
import os
import sgtk
from tank_vendor import six
import glob
import tde4

HookBaseClass = sgtk.get_hook_baseclass()


class Tde4SessionCollector(HookBaseClass):
    """
    A basic collector that handles files and general objects.

    This collector hook is used to collect individual files that are browsed or
    dragged and dropped into the Publish2 UI. It can also be subclassed by other
    collectors responsible for creating items for a file to be published such as
    the current Maya session file.

    This plugin centralizes the logic for collecting a file, including
    determining how to display the file for publishing (based on the file
    extension).

    In addition to creating an item to publish, this hook will set the following
    properties on the item::

        path - The path to the file to publish. This could be a path
            representing a sequence of files (including a frame specifier).

        sequence_paths - If the item represents a collection of files, the
            plugin will populate this property with a list of files matching
            "path".

    """

    @property
    def common_file_info(self):
        """
        A dictionary of file type info that allows the basic collector to
        identify common production file types and associate them with a display
        name, item type, and config icon.

        The dictionary returned is of the form::

            {
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                <Publish Type>: {
                    "extensions": [<ext>, <ext>, ...],
                    "icon": <icon path>,
                    "item_type": <item type>
                },
                ...
            }

        See the collector source to see the default values returned.

        Subclasses can override this property, get the default values via
        ``super``, then update the dictionary as necessary by
        adding/removing/modifying values.
        """

        if not hasattr(self, "_common_file_info"):

            # do this once to avoid unnecessary processing
            self._common_file_info = {
                "Alias File": {
                    "extensions": ["wire"],
                    "icon": self._get_icon_path("alias.png"),
                    "item_type": "file.alias",
                },
                "Alembic Cache": {
                    "extensions": ["abc"],
                    "icon": self._get_icon_path("alembic.png"),
                    "item_type": "file.alembic",
                },
                "3dsmax Scene": {
                    "extensions": ["max"],
                    "icon": self._get_icon_path("3dsmax.png"),
                    "item_type": "file.3dsmax",
                },
                "Hiero Project": {
                    "extensions": ["hrox"],
                    "icon": self._get_icon_path("hiero.png"),
                    "item_type": "file.hiero",
                },
                "Houdini Scene": {
                    "extensions": ["hip", "hipnc"],
                    "icon": self._get_icon_path("houdini.png"),
                    "item_type": "file.houdini",
                },
                "Maya Scene": {
                    "extensions": ["ma", "mb"],
                    "icon": self._get_icon_path("maya.png"),
                    "item_type": "file.maya",
                },
                "Motion Builder FBX": {
                    "extensions": ["fbx"],
                    "icon": self._get_icon_path("motionbuilder.png"),
                    "item_type": "file.motionbuilder",
                },
                "Nuke Script": {
                    "extensions": ["nk"],
                    "icon": self._get_icon_path("nuke.png"),
                    "item_type": "file.nuke",
                },
                "Photoshop Image": {
                    "extensions": ["psd", "psb"],
                    "icon": self._get_icon_path("photoshop.png"),
                    "item_type": "file.photoshop",
                },
                "VRED Scene": {
                    "extensions": ["vpb", "vpe", "osb"],
                    "icon": self._get_icon_path("vred.png"),
                    "item_type": "file.vred",
                },
                "Rendered Image": {
                    "extensions": ["dpx", "exr"],
                    "icon": self._get_icon_path("image_sequence.exr"),
                    "item_type": "file.image",
                },
                "Texture Image": {
                    "extensions": ["tif", "tiff", "tx", "tga", "dds", "rat"],
                    "icon": self._get_icon_path("texture.png"),
                    "item_type": "file.texture",
                },
                "PDF": {
                    "extensions": ["pdf"],
                    "icon": self._get_icon_path("file.png"),
                    "item_type": "file.image",
                },
                "Katana Scene": {
                    "extensions": ["katana"],
                    "icon": self._get_icon_path("katana.png"),
                    "item_type": "file.katana",
                },
                "3de Scene": {
                    "extensions": ["3de"],
                    "icon": self._get_icon_path("icon_256.png"),
                    "item_type": "file.3de",
                },
                "Image": {
                    "extensions": ["tif", "tiff", "jpeg", "jpg", "png", "exr"],
                    "icon": self._get_icon_path("icon_256.png"),
                    "item_type": "file.image",
                },
                "Mel Script": {
                    "extensions": ["mel"],
                    "icon": self._get_icon_path("icon_256.png"),
                    "item_type": "file.mel",
                },
            }

        return self._common_file_info

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """
        # grab any base class settings
        collector_settings = super(Tde4SessionCollector, self).settings or {}

        # settings specific to this collector
        tde4_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(tde4_session_settings)

        # print("##########################################################")
        # print("COLLECTOR.PY Settings -> Collector_Settings  %s-> "%(collector_settings))
        # print("##########################################################")

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current scene open in a DCC and parents a subtree of items
        under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """
        # print("COLLECTOR TK-KATANA")


        # default implementation does not do anything
        item = self.collect_current_tde4_session(settings, parent_item)
        project_root = item.properties["project_root"]
        path = item.properties["path"]

        # look at the render layers to find rendered images on disk
        #self.collect_rendered_images(item)

        # self.collect_mel_script(item, project_root)

        # print("##########################################################")
        # print("COLLECTOR.PY process_current_session -> project_root %s-> "%(project_root))
        # print("COLLECTOR.PY process_current_session -> item %s-> "%(item))
        # print("COLLECTOR.PY process_current_session -> path %s-> "%(path))
        # print("COLLECTOR.PY process_current_session -> parent_item %s-> "%(parent_item))
        # print("##########################################################")

        # if we can determine a project root, collect other files to publish
        # if project_root:

        #     self.logger.info(
        #         "Current 3DE4 project is: %s." % (project_root,),
        #         extra={
        #             "action_button": {
        #                 "label": "Change Project",
        #                 "tooltip": "Change to a different 3DE4 project",
        #                 "callback": lambda: tde4.getProjectPath(),
        #             }
        #         },
        #     )

        #     #self.collect_mel_script(item, project_root)
        #     # self.collect_playblasts(item, project_root)
        #     # self.collect_alembic_caches(item, project_root)
        # else:

        #     self.logger.info(
        #         "Could not determine the current 3DE4 project.",
        #         extra={
        #             "action_button": {
        #                 "label": "Set Project",
        #                 "tooltip": "Set the 3DE4 project",
        #                 "callback": lambda: tde4.getProjectPath(),
        #             }
        #         },
        #     )

        # if cmds.ls(geometry=True, noIntermediate=True):
        #     self._collect_session_geometry(item)
        # if project_root:
        self.collect_mel_script(item,project_root)
        self.collect_nuke_script(item,project_root)

    def collect_rendered_images(self,parent_item):
            """
            Creates items for any rendered images that can be identified by
            render layers in the file.

            :param parent_item: Parent Item instance
            :return:
            """

            rodNode = NodegraphAPI.GetNode('ROD_primary_diskRender') 
            renderLocationParamValue = rodNode.getParameter('args.renderSettings.outputs.outputName.locationSettings.renderLocation.value') 
            rpbParamValue = renderLocationParamValue.getValue(0) 
            render_path = rpbParamValue
            base_path = os.path.dirname(os.path.abspath(str(rpbParamValue)))

            # iterate over defined render layers and query the render settings for
            # information about a potential render
            # for layer in cmds.ls(type="renderLayer"):

            #     self.logger.info("Processing render layer: %s" % (layer,))

            #     # use the render settings api to get a path where the frame number
            #     # spec is replaced with a '*' which we can use to glob
            #     (frame_glob,) = cmds.renderSettings(
            #         genericFrameImageName="*", fullPath=True, layer=layer
            #     )

            # see if there are any files on disk that match this pattern
            rendered_paths = render_path

            if rendered_paths:
                # we only need one path to publish, so take the first one and
                # let the base class collector handle it

                # item_info = super(KatanaSessionCollector, self)._get_item_info(path)
                # item_type = "%s.sequence" % (item_info["item_type"],)
                # type_display = "%s Sequence" % (item_info["type_display"],)

                item = super(Tde4SessionCollector, self)._collect_file(
                    parent_item, rendered_paths, frame_sequence=True
                )
                layer = "renderLocation"
                # the item has been created. update the display name to include
                # the an indication of what it is and why it was collected
                item.name = "%s (Render Node: %s)" % (item.name, layer)

                # print("##########################################################")
                # print("COLLECTOR.PY collect_Render -> item.name  %s-> "%(item.name))
                # print("##########################################################")

            # # create the session item for the publish hierarchy
            # display_name = os.path.basename(path)
            # session_item = parent_item.create_item(
            #     item_type,
            #     type_display,
            #     item.name
            # )
            # session_item.properties["path"] = rendered_paths      

    def collect_current_tde4_session(self, settings, parent_item):
        """
        Creates an item that represents the current 3de session.

        :param parent_item: Parent Item instance

        :returns: Item of type katna.session
        """
        publisher = self.parent
        path = tde4.getProjectPath()
        
        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current 3de Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "3de.session", "3DE Session", display_name
        )
        session_item.properties["path"] = path

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, os.pardir, "icons", "icon_256.png")
        session_item.set_icon_from_path(icon_path)

        # discover the project root which helps in discovery of other
        # publishable items
        # project_root = cmds.workspace(q=True, rootDirectory=True)
        project_root = os.path.dirname(os.path.abspath(path))
        session_item.properties["project_root"] = "project_root"
 
        # if a work template is defined, add it to the item properties so
        # that it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:

            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for 3de4 collection.")

        self.logger.info("Collected current 3de4 scene")

        # print("##########################################################")
        # print("COLLECTOR.PY collect_current_3de4_session session_item.properties[project_root] %s-> "%(session_item.properties["project_root"]))
        # print("COLLECTOR.PY collect_current_3de4_session session_item.properties[path] %s-> "%(session_item.properties["path"]))
        # print("COLLECTOR.PY collect_current_3de4_session work_template_setting  %s-> "%(work_template_setting ))
        # print("COLLECTOR.PY collect_current_3de4_session %s-> "%(path))
        # print("##########################################################")

        return session_item        

    def process_file(self, settings, parent_item, path):
        """
        Analyzes the given file and creates one or more items
        to represent it.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        :param path: Path to analyze

        :returns: The main item that was created, or None if no item was created
            for the supplied path
        """

        # handle files and folders differently
        if os.path.isdir(path):
            self._collect_folder(parent_item, path)
            return None
        else:
            return self._collect_file(parent_item, path)

    def getParentDir(path, level=1):
        return os.path.normpath( os.path.join(path, *([".."] * level)) )

    def collect_mel_script(self, parent_item, project_root):
        """
            export mel script from Tde4
        """
        # exports mel
        rootPrj = getParentDir(project_root, 3)
        mel_dir = os.path.join(rootPrj, "maya_export")
        if not os.path.exists(mel_dir):
            return

        self.logger.info(
            "Processing melfolder: %s" % (mel_dir,),
            extra={"action_show_folder": {"path": mel_dir}},
        )

        # look for mel script files in the maya_export folder
        for filename in os.listdir(mel_dir):
            mel_script_path = os.path.join(mel_dir, filename)
            # do some early pre-processing to ensure the file is of the right
            # type. use the base class item info method to see what the item
            # type would be.
            # item_info = self._get_item_info(filename)
            mel_item = parent_item.create_item(
                "file.mel", "mel"
            )
            # allow the base class to collect and create the item. it knows how
            # to handle files
            item = super(Tde4SessionCollector, self)._collect_file(parent_item, mel_script_path)
            if item.info["item_type"] != "file.mel":
                continue
            # the item has been created. update the display name to
            # include the node path to make it clear to the user how it
            # was collected within the current session.
            item.name = "%s (%s)" % (item.name, mel_script_path)
            # super(Tde4SessionCollector, self)._collect_file(parent_item, mel_script_path)

    def collect_nuke_script(self, parent_item, project_root):
        """
            export mel script from Tde4
        """
        # exports mel 
        rootPrj = getParentDir(project_root, 3)
        nuke_dir = os.path.join(rootPrj, "nuke_export")
        if not os.path.exists(nuke_dir):
            return

        self.logger.info(
            "Processing nuke folder: %s" % (nuke_dir,),
            extra={"action_show_folder": {"path": nuke_dir}},
        )

        # look for mel script files in the maya_export folder
        for filename in os.listdir(nuke_dir):
            nuke_script_path = os.path.join(nuke_dir, filename)
            # do some early pre-processing to ensure the file is of the right
            # type. use the base class item info method to see what the item
            # type would be.
            # item_info = self._get_item_info(filename)
            nuke_item = parent_item.create_item(
                "file.nk", "nk"
            )
            # allow the base class to collect and create the item. it knows how
            # to handle alembic files
            item = super(Tde4SessionCollector, self)._collect_file(parent_item, nuke_script_path)
            if item.info["item_type"] != "file.nk":
                continue
            item.name = "%s (%s)" % (item.name, nuke_script_path)
            # super(Tde4SessionCollector, self)._collect_file(parent_item, nuke_script_path)

    def _collect_file(self, parent_item, path, frame_sequence=False):
        """
        Process the supplied file path.

        :param parent_item: parent item instance
        :param path: Path to analyze
        :param frame_sequence: Treat the path as a part of a sequence
        :returns: The item that was created
        """
        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        publisher = self.parent

        # get info for the extension
        item_info = self._get_item_info(path)
        item_type = item_info["item_type"]
        type_display = item_info["type_display"]
        evaluated_path = path
        is_sequence = False

        if frame_sequence:
            # replace the frame number with frame spec
            seq_path = publisher.util.get_frame_sequence_path(path)
            if seq_path:
                evaluated_path = seq_path
                type_display = "%s Sequence" % (type_display,)
                item_type = "%s.%s" % (item_type, "sequence")
                is_sequence = True

        display_name = publisher.util.get_publish_name(path, sequence=is_sequence)

        # print("#################################################################")
        # print("COLLECTOR - > COLLECT FILE SEQ \n")
        # print("evaluated_path -> %s \n"%(evaluated_path))
        # print("type_display -> %s \n"%(type_display))
        # print("item_type -> %s \n"%(item_type))
        # print("#################################################################")

        # create and populate the item
        file_item = parent_item.create_item(item_type, type_display, display_name)
        file_item.set_icon_from_path(item_info["icon_path"])

        # if the supplied path is an image, use the path as the thumbnail.
        if item_type.startswith("file.image") or item_type.startswith("file.texture"):
            file_item.set_thumbnail_from_path(path)

            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False

        # all we know about the file is its path. set the path in its
        # properties for the plugins to use for processing.
        file_item.properties["path"] = evaluated_path

        if is_sequence:
            # include an indicator that this is an image sequence and the known
            # file that belongs to this sequence
            file_item.properties["sequence_paths"] = [path]

        self.logger.info("Collected file: %s" % (evaluated_path,))

        return file_item

    def _collect_folder(self, parent_item, folder):
        """
        Process the supplied folder path.

        :param parent_item: parent item instance
        :param folder: Path to analyze
        :returns: The item that was created
        """

        # make sure the path is normalized. no trailing separator, separators
        # are appropriate for the current os, no double separators, etc.
        folder = sgtk.util.ShotgunPath.normalize(folder)

        publisher = self.parent
        img_sequences = publisher.util.get_frame_sequences(
            folder, self._get_image_extensions()
        )

        file_items = []

        for (image_seq_path, img_seq_files) in img_sequences:

            # get info for the extension
            item_info = self._get_item_info(image_seq_path)
            item_type = item_info["item_type"]
            type_display = item_info["type_display"]

            # the supplied image path is part of a sequence. alter the
            # type info to account for this.
            type_display = "%s Sequence" % (type_display,)
            item_type = "%s.%s" % (item_type, "sequence")
            icon_name = "image_sequence.png"

            # get the first frame of the sequence. we'll use this for the
            # thumbnail and to generate the display name
            img_seq_files.sort()
            first_frame_file = img_seq_files[0]
            display_name = publisher.util.get_publish_name(
                first_frame_file, sequence=True
            )

            # create and populate the item
            file_item = parent_item.create_item(item_type, type_display, display_name)
            icon_path = self._get_icon_path(icon_name)
            file_item.set_icon_from_path(icon_path)

            # use the first frame of the seq as the thumbnail
            file_item.set_thumbnail_from_path(first_frame_file)

            # disable thumbnail creation since we get it for free
            file_item.thumbnail_enabled = False

            # all we know about the file is its path. set the path in its
            # properties for the plugins to use for processing.
            file_item.properties["path"] = image_seq_path
            file_item.properties["sequence_paths"] = img_seq_files

            self.logger.info("Collected file: %s" % (image_seq_path,))

            file_items.append(file_item)

        if not file_items:
            self.logger.warn("No image sequences found in: %s" % (folder,))

        return file_items

    def _get_item_info(self, path):
        """
        Return a tuple of display name, item type, and icon path for the given
        filename.

        The method will try to identify the file as a common file type. If not,
        it will use the mimetype category. If the file still cannot be
        identified, it will fallback to a generic file type.

        :param path: The file path to identify type info for

        :return: A dictionary of information about the item to create::

            # path = "/path/to/some/file.0001.exr"

            {
                "item_type": "file.image.sequence",
                "type_display": "Rendered Image Sequence",
                "icon_path": "/path/to/some/icons/folder/image_sequence.png",
                "path": "/path/to/some/file.%04d.exr"
            }

        The item type will be of the form `file.<type>` where type is a specific
        common type or a generic classification of the file.
        """

        publisher = self.parent

        # extract the components of the supplied path
        file_info = publisher.util.get_file_path_components(path)
        extension = file_info["extension"]
        filename = file_info["filename"]

        # default values used if no specific type can be determined
        type_display = "File"
        item_type = "file.unknown"

        # keep track if a common type was identified for the extension
        common_type_found = False

        icon_path = None

        # look for the extension in the common file type info dict
        for display in self.common_file_info:
            type_info = self.common_file_info[display]

            if extension in type_info["extensions"]:
                # found the extension in the common types lookup. extract the
                # item type, icon name.
                type_display = display
                item_type = type_info["item_type"]
                icon_path = type_info["icon"]
                common_type_found = True
                break

        if not common_type_found:
            # no common type match. try to use the mimetype category. this will
            # be a value like "image/jpeg" or "video/mp4". we'll extract the
            # portion before the "/" and use that for display.
            (category_type, _) = mimetypes.guess_type(filename)

            if category_type:

                # mimetypes.guess_type can return unicode strings depending on
                # the system's default encoding. If a unicode string is
                # returned, we simply ensure it's utf-8 encoded to avoid issues
                # with toolkit, which expects utf-8
                category_type = six.ensure_str(category_type)

                # the category portion of the mimetype
                category = category_type.split("/")[0]

                type_display = "%s File" % (category.title(),)
                item_type = "file.%s" % (category,)
                icon_path = self._get_icon_path("%s.png" % (category,))

        # fall back to a simple file icon
        if not icon_path:
            icon_path = self._get_icon_path("file.png")

        # everything should be populated. return the dictionary
        return dict(
            item_type=item_type,
            type_display=type_display,
            icon_path=icon_path,
        )

    def _get_icon_path(self, icon_name, icons_folders=None):
        """
        Helper to get the full path to an icon.

        By default, the app's ``hooks/icons`` folder will be searched.
        Additional search paths can be provided via the ``icons_folders`` arg.

        :param icon_name: The file name of the icon. ex: "alembic.png"
        :param icons_folders: A list of icons folders to find the supplied icon
            name.

        :returns: The full path to the icon of the supplied name, or a default
            icon if the name could not be found.
        """

        # ensure the publisher's icons folder is included in the search
        app_icon_folder = os.path.join(self.disk_location, "icons")

        # build the list of folders to search
        if icons_folders:
            icons_folders.append(app_icon_folder)
        else:
            icons_folders = [app_icon_folder]

        # keep track of whether we've found the icon path
        found_icon_path = None

        # iterate over all the folders to find the icon. first match wins
        for icons_folder in icons_folders:
            icon_path = os.path.join(icons_folder, icon_name)
            if os.path.exists(icon_path):
                found_icon_path = icon_path
                break

        # supplied file name doesn't exist. return the default file.png image
        if not found_icon_path:
            found_icon_path = os.path.join(app_icon_folder, "file.png")

        return found_icon_path

    def _get_image_extensions(self):

        if not hasattr(self, "_image_extensions"):

            image_file_types = ["Photoshop Image", "Rendered Image", "Texture Image"]
            image_extensions = set()

            for image_file_type in image_file_types:
                image_extensions.update(
                    self.common_file_info[image_file_type]["extensions"]
                )

            # get all the image mime type image extensions as well
            mimetypes.init()
            types_map = mimetypes.types_map
            for (ext, mimetype) in types_map.items():
                if mimetype.startswith("image/"):
                    image_extensions.add(ext.lstrip("."))

            self._image_extensions = list(image_extensions)

        return self._image_extensions
