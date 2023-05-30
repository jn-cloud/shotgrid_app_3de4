# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import shutil
import sgtk
from sgtk.util.filesystem import ensure_folder_exists

import tde4


HookBaseClass = sgtk.get_hook_baseclass()


class Tde4ExportMelPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open 3de4 session.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_session.py"

    """
    @property
    def name(self):
        """The general name for this plugin (:class:`str`)."""
        return "Tde4ExportMelPublishPlugin"

    @property
    def icon(self):
        """
        The path to an icon on disk that is representative of this plugin
        (:class:`str`).
        """
        return os.path.join(self.disk_location, "icons", "icon_256.png")

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        loader_url = "https://support.shotgunsoftware.com/hc/en-us/articles/219033078"

        return """
        Publishes the Mel file to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the file's current
        path on disk. If a publish template is configured, a copy of the
        current session will be copied to the publish template path which
        will be the file that is published. Other users will be able to access
        the published file via the <b><a href='%s'>Loader</a></b> so long as
        they have access to the file's location on disk.

        If the session has not been saved, validation will fail and a button
        will be provided in the logging output to save the file.

        <h3>File versioning</h3>
        If the filename contains a version number, the process will bump the
        file to the next version after publishing.

        The <code>version</code> field of the resulting <b>Publish</b> in
        Shotgun will also reflect the version number identified in the filename.
        The basic worklfow recognizes the following version formats by default:

        <ul>
        <li><code>filename.v###.ext</code></li>
        <li><code>filename_v###.ext</code></li>
        <li><code>filename-v###.ext</code></li>
        </ul>

        After publishing, if a version number is detected in the work file, the
        work file will automatically be saved to the next incremental version
        number. For example, <code>filename.v001.ext</code> will be published
        and copied to <code>filename.v002.ext</code>

        If the next incremental version of the file already exists on disk, the
        validation step will produce a warning, and a button will be provided in
        the logging output which will allow saving the session to the next
        available version number prior to publishing.

        <br><br><i>NOTE: any amount of version number padding is supported. for
        non-template based workflows.</i>

        <h3>Overwriting an existing publish</h3>
        In non-template workflows, a file can be published multiple times,
        however only the most recent publish will be available to other users.
        Warnings will be provided during validation if there are previous
        publishes.
        """ % (loader_url,)

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

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

        # inherit the settings from the base publish plugin
        base_settings = super(Tde4ExportMelPublishPlugin, self).settings or {}

        # settings specific to this class
        tde4_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            }
        }

        # update the base settings
        base_settings.update(tde4_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["3de.*", "file.mel"]
        """
        return ["3de.session","file.mel"]
        # return ["3de.session.file.mel"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        # item.context_change_allowed = True
        # if a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.
        if settings.get("Publish Template").value:
            item.context_change_allowed = False

        path = _session_path()

        if not path:
            # the session has not been saved before (no path determined).
            # provide a save button. the session will need to be saved before
            # validation will succeed.
            self.logger.warn(
                "The mel session has not been saved.",
                extra=_get_save_as_action()
            )

        self.logger.info(
            "mel '%s' plugin accepted the current mel session." %
            (self.name,)
        )
        return {
            "accepted": True,
            "checked": True,
            "visible": True,
        }

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values ar e`Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        publisher = self.parent

        path = _session_path()
        # ---- ensure the session has been saved

        if not path:
            # the session still requires saving. provide a save button.
            # validation fails.
            error_msg = "The 3de4 session has not been saved."
            self.logger.error(
                error_msg,
                extra=_get_save_as_action()
            )
            raise Exception(error_msg)

        # ---- check the session against any attached work template

        # get the path in a normalized state. no trailing separator,
        # separators are appropriate for current os, no double separators,
        # etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        # if the session item has a known work template, see if the path
        # matches. if not, warn the user and provide a way to save the file to
        # a different path
        work_template = item.properties.get("work_template")
        if work_template:
            
            if not work_template.validate(path):
                self.logger.warning(
                    "The current session does not match the configured work "
                    "file template.",
                    extra={
                        "action_button": {
                            "label": "Save File",
                            "tooltip": "Save the current 3de session to a "
                                       "different file name",
                            # will launch wf2 if configured
                            "callback": _get_save_as_action()
                        }
                    }
                )
            else:
                self.logger.debug(
                    "Work template configured and matches session file.")
        else:
            self.logger.debug("No work template configured.")

        # ---- see if the version can be bumped post-publish

        # check to see if the next version of the work file already exists on
        # disk. if so, warn the user and provide the ability to jump to save
        # to that version now
        (next_version_path, version) = self._get_next_version_info(path, item)
        if next_version_path and os.path.exists(next_version_path):

            # determine the next available version_number. just keep asking for
            # the next one until we get one that doesn't exist.
            while os.path.exists(next_version_path):
                (next_version_path, version) = self._get_next_version_info(
                    next_version_path, item)

            error_msg = "The next version of this file already exists on disk."
            self.logger.error(
                error_msg,
                extra={
                    "action_button": {
                        "label": "Save to v%s" % (version,),
                        "tooltip": "Save to the next available version number, "
                                   "v%s" % (version,),
                        "callback": lambda: _save_session(next_version_path)
                    }
                }
            )
            raise Exception(error_msg)

        # ---- populate the necessary properties and call base class validation
        # populate the publish template on the item if found
        publish_template_setting = settings.get("Publish Template")
        publish_template = publisher.engine.get_template_by_name(
            publish_template_setting.value)
        if publish_template:
            item.properties["publish_template"] = publish_template
          
        # set the session path on the item for use by the base plugin validation
        # step. NOTE: this path could change prior to the publish phase.
        item.properties["path"] = path
        return super(Tde4ExportMelPublishPlugin, self).validate(settings, item)
    
    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        # get the path in a normalized state. no trailing separator, separators
        # are appropriate for current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(_session_path())

        # ensure the session is saved
        _save_session(path)

        # update the item with the saved session path
        item.properties["path"] = path

        # add dependencies for the base class to register when publishing
        item.properties["publish_dependencies"] = _3de4_find_additional_session_dependencies()

        try:
            # excecute export mel 
            _export_mel(path)
        except Exception:
            raise Exception("Unable to export mel script")
        

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        publisher = self.parent
 
        path = sgtk.util.ShotgunPath.normalize(_session_path())
        item.properties["path"] = path

        #since we publish script using sgtk we get a few publish data to fill
        Tpublish_name = self.get_publish_name(settings, item)
        publish_version = self.get_publish_version(settings, item)

        publish_name, Item_file_extension = os.path.splitext(Tpublish_name)
        publish_name = publish_name
        publish_fl_name = publish_name + "_v" + str(publish_version).zfill(3) + ".mel"

        #get path from a specified template
        Mpublish_path = self.get_SpecificTemplatePublishPath(path,publish_version,"3de4_shot_mel_export")

        publishedMelPath = os.path.join(os.path.abspath(Mpublish_path),publish_fl_name)

        #copy published mel script to the correct folder
        try:
            _copyToMelPath(path,Mpublish_path)
        except Exception:
            raise Exception("Unable to export mel script")

        try:
            sgtk.util.register_publish(publisher.sgtk,
                                    item.context,
                                    publishedMelPath,
                                    publish_fl_name,
                                    publish_version,
                                    published_file_type = "Mel Script")
        except Exception:
            raise Exception("Unable to publish mel script")

    #path request for a specific template 
    def get_SpecificTemplatePublishPath(self,path,version,specificTemplate):
        path = os.path.abspath(path)
        specificTemplate = str(specificTemplate)
        current_engine = sgtk.platform.current_engine()
        tk = current_engine.sgtk
        ctx = tk.context_from_path(path)
        template = tk.templates[specificTemplate]
        fields = ctx.as_template_fields(template)
        fields["version"] = version
        pPublish_path = template.apply_fields(fields)

        #for adding the task name to the publish name fields
        pPublish_path = pPublish_path.rsplit('/',1)[0]
        
        return pPublish_path


def _3de4_find_additional_session_dependencies():
    """
    Find additional dependencies from the session
    """
    # Figure out what read nodes are known to the engine and use them
    # as dependencies

    #runs the py for exporting as mel
    return []


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    path = tde4.getProjectPath()
    return path

def _save_session(path):
    """
    Save the current session to the supplied path.
    """
    # Ensure that the folder is created when saving
    ensure_folder_exists(os.path.dirname(path))

def _get_save_as_action():
    """
    Simple helper for returning a log action dict for saving the session
    """
    engine = sgtk.platform.current_engine()
    callback = _save_as

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current session",
            "callback": callback
        }
    }

def _save_as():
    path = tde4.getProjectPath()
    tde4.saveProject(path)

def _export_mel(path):
    """
    Exports Mel file from 3de4 to maya 
    """
    import builtins as builtin
    from export_maya import _maya_export_mel_file

    campg	= None
    pgl	= tde4.getPGroupList()
    for pg in pgl:
        if tde4.getPGroupType(pg)=="CAMERA": campg = pg

    cam	= tde4.getCurrentCamera()
    offset	= tde4.getCameraFrameOffset(cam)
    startFrame = builtin.float(builtin.str(offset))

    camera_selection = 5 
    model_selection = 1 

    overscan_w_pc = 1.0 
    overscan_h_pc = 1.0 
    export_material = 0 
    camera_list = tde4.getCameraList()

    #1 : cm -> cm,2 : cm -> m, 3 : cm -> mm,4 : cm -> in,5 : cm -> ft,6 : cm -> yd
    unit_scales = {1 : 1.0,2 : 0.01,  3 : 10.0, 4 : 0.393701, 5 : 0.0328084, 6 : 0.0109361} 
    unit_scale_factor = unit_scales[1.0]

    if camera_selection == 1:
        camera_list = [tde4.getCurrentCamera()]
    elif camera_selection == 2:
        camera_list = tde4.getCameraList(1)
    elif camera_selection == 3:
        camera_list = []
        tcl =  tde4.getCameraList()
        for c in tcl:
            if tde4.getCameraType(c) == "SEQUENCE":
                camera_list.append(c)
    elif camera_selection == 4:
        camera_list = []
        tcl =  tde4.getCameraList()
        for c in tcl:
            if tde4.getCameraType(c) == "REF_FRAME":
                camera_list.append(c)

    path	= path 
    frame0	= startFrame 
    frame0	-= 1
    hide_ref= 0 

    _maya_export_mel_file(path,campg,camera_list,model_selection,overscan_w_pc,overscan_h_pc,export_material,unit_scale_factor,frame0,hide_ref)

def processFileClean(MelExport_path):
    extractNm = "."+MelExport_path.rsplit('.',2)[1]
    cleanFileNm = MelExport_path.replace(extractNm,"")
    shutil.move(os.path.abspath(MelExport_path),os.path.abspath(cleanFileNm))

def copyToExport(MelExport_path,MelFilePath):
    if os.path.exists(os.path.abspath(MelExport_path)):
        mv = shutil.move(os.path.abspath(MelFilePath), os.path.abspath(MelExport_path))
        processFileClean(mv)
    
def _copyToMelPath(s_path,melExpPath):
    ensure_folder_exists(os.path.abspath(melExpPath))
    melFilePath = s_path +".mel" 
    if os.path.isfile(os.path.abspath(melFilePath)):
        copyToExport(melExpPath,melFilePath)
