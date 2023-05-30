# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk

import os
import shutil
import sgtk
from sgtk.util.filesystem import ensure_folder_exists


import tde4
from export_maya import *

HookBaseClass = sgtk.get_hook_baseclass()

project_name = "katana_sg_dev"

class PostPhaseMelHook(HookBaseClass):
    """
    This hook defines methods that are executed after each phase of a publish:
    validation, publish, and finalization. Each method receives the publish
    tree instance being used by the publisher, giving full control to further
    curate the publish tree including the publish items and the tasks attached
    to them. See the :class:`PublishTree` documentation for additional details
    on how to traverse the tree and manipulate it.
    """

    # See the developer docs for more information about the methods that can be
    # defined here: https://developer.shotgridsoftware.com/tk-multi-publish2/

    @property
    def name(self):
        """The general name for this plugin (:class:`str`)."""
        return "PostPhaseMelHook"

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
        Publishes the file to Shotgun. A <b>Publish</b> entry will be
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
        base_settings = super(PostPhaseMelHook, self).settings or {}

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

 
    def post_finalize(self,publish_tree):
        for item in publish_tree:
            boolv = item.checked
            pname = project_name = self.parent.context.project["name"]
            print("#################################################################################")
            print("POST FILES ITEM -> %s"%item)
            print("POST FILES ITEM CHECHED -> %s"%boolv)
            print("POST FILES PROJECT NAME -> %s"%pname)
            print("#################################################################################")
            # if not item.checked:
            #     continue
            for task in item.tasks:
                # if not task.active:
                #     continue
                print("#################################################################################")
                print("POST FILES IN TASK -> %s"%task)
                print("#################################################################################")
                for ts in task.settings:
                    print("#################################################################################")
                    print("POST FILES IN TASK SETTINGS -> %s"%ts)
                    print("#################################################################################")
                # if task.settings["Export 3de4 to Mel"].value is True:
                #     print("#################################################################################")
                #     print("POST FILES Task.Settings-> %s"%task)
                #     #print("POST FILES Task.SettingsEXPORTTOMEL-> %s"%expm)
                #     print("#################################################################################")
     
    def _session_path():
        """
        Return the path to the current session
        :return:
        """
        path = tde4.getProjectPath()
        return path

