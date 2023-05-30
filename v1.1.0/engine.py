"""
A 3dequalizer4 engine for Tank.

"""
from __future__ import print_function
import datetime
import logging
import os
import re
import shutil
import subprocess
import sys

import sgtk
from sgtk.platform import Engine


class TDE4Engine(Engine):

    @property
    def context_change_allowed(self):
        """
        Whether a context change is allowed without the need for a restart.
        If a bundle supports on-the-fly context changing, this property should
        be overridden in the deriving class and forced to return True.
        :returns: bool
        """
        return True

    @property
    def host_info(self):
        """
        Returns information about the application hosting this engine.
        This should be re-implemented in deriving classes to handle the logic
        specific to the application the engine is designed for.
        A dictionary with at least a "name" and a "version" key should be returned
        by derived implementations, with respectively the host application name
        and its release string as values, e.g. ``{ "name": "Maya", "version": "2017.3"}``.
        :returns: A ``{"name": "unknown", "version" : "unknown"}`` dictionary.
        """
        host_info = {"name": "3DEqualizer4", "version": "unknown"}
        try:
            import tde4
            host_info["name"], host_info["version"] = re.match(
                "^([^\s]+)\s+(.*)$", tde4.get3DEVersion()
            ).groups()
        except:
            # Fallback to initialized above
            pass

        return host_info

    def create_shotgun_menu(self):
        """
        Create the shotgun menu
        """
        if self.has_ui:
            self.register_command(
                "Jump to Shotgun",
                self._jump_to_shotgun,
                {
                    "short_name": "jump_to_sg",
                    "description": "Jump to Entity page in Shotgun.",
                    "type": "context_menu",
                },
            )
            self.register_command(
                "Jump to File System",
                self._jump_to_filesystem,
                {
                    "short_name": "jump_to_fs",
                    "description": "Open relevant folders in the file system.",
                    "type": "context_menu",
                },
            )
            # self.register_command(
            #     "Export Mel",
            #     self._export_mel,
            #     {
            #         "short_name": "export_mel",
            #         "description": "Exports mel from 3de4 to maya.",
            #         "type": "context_menu",
            #     },
            # )
            tk_3de4 = self.import_module("tk_3de4")
            menu_generator = tk_3de4.MenuGenerator(self)
            menu_generator.create_menu()

            import tde4
            tde4.rescanPythonDirs()

            return True
        return False

    def post_app_init(self):
        """
        Executed by the system and typically implemented by deriving classes.
        This method called after all apps have been loaded.
        """
        self.create_shotgun_menu()

    def post_qt_init(self):
        """
        Called after the initialization of qt within startup.py.
        """
        self._initialize_dark_look_and_feel()

    def post_context_change(self, old_context, new_context):
        """
        Called after a context change.
        Implemented by deriving classes.
        :param old_context:     The context being changed away from.
        :type old_context: :class:`~sgtk.Context`
        :param new_context:     The context being changed to.
        :type new_context: :class:`~sgtk.Context`
        """
        self.create_shotgun_menu()

    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        Implemented by deriving classes.
        """
        self.logger.debug("%s: Destroying...", self)
        self._cleanup_folders()

    @property
    def has_ui(self):
        """
        Indicates that the host application that the engine is connected to has a UI enabled.
        This always returns False for some engines (such as the shell engine) and may vary
        for some engines, depending if the host application for example is in batch mode or
        UI mode.
        :returns: boolean value indicating if a UI currently exists
        """
        return True

    ##########################################################################################
    # logging

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available.
        All log messages from the toolkit logging namespace will be passed to this method.
        .. note:: To implement logging in your engine implementation, subclass
                  this method and display the record in a suitable way - typically
                  this means sending it to a built-in DCC console. In addition to this,
                  ensure that your engine implementation *does not* subclass
                  the (old) :meth:`Engine.log_debug`, :meth:`Engine.log_info` family
                  of logging methods.
                  For a consistent output, use the formatter that is associated with
                  the log handler that is passed in. A basic implementation of
                  this method could look like this::
                      # call out to handler to format message in a standard way
                      msg_str = handler.format(record)
                      # display message
                      print msg_str
        .. warning:: This method may be executing called from worker threads. In DCC
                     environments, where it is important that the console/logging output
                     always happens in the main thread, it is recommended that you
                     use the :meth:`async_execute_in_main_thread` to ensure that your
                     logging code is writing to the DCC console in the main thread.
        :param handler: Log handler that this message was dispatched from
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Std python logging record
        :type record: :class:`~python.logging.LogRecord`
        """
        log_debug = record.levelno < logging.INFO and sgtk.LogManager().global_debug
        log_info_above = record.levelno >= logging.INFO
        if log_debug or log_info_above:
            msg = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            print(msg, handler.format(record))

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Create a TankQDialog with the specified widget embedded. This also connects to the
        dialogs dialog_closed event so that it can clean up when the dialog is closed.
        .. note:: For more information, see the documentation for :meth:`show_dialog()`.
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :type widget: :class:`PySide.QtGui.QWidget`
        """
        from sgtk.platform.qt import QtCore
        dialog = super(TDE4Engine, self)._create_dialog(title, bundle, widget, parent)
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        dialog.setWindowState(
            (dialog.windowState() & ~QtCore.Qt.WindowMinimized) | QtCore.Qt.WindowActive)
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    #########################################################################################
    # callbacks

    def _jump_to_shotgun(self):
        """
        Jump to shotgun, launch web browser
        """
        from sgtk.platform.qt import QtCore, QtGui
        url = self.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _jump_to_filesystem(self):
        """
        Jump from context to the filesystem
        """
        # launch one window for each location on disk
        paths = self.context.filesystem_locations
        # get the setting
        system = sys.platform
        # run the app
        if system == "linux2" or system == "linux":
            cmd = ["xdg-open"]
        elif system == "darwin":
            cmd = ["open"]
        elif system == "win32":
            cmd = ["cmd.exe", "/C", "start", "Folder"]
        else:
            raise Exception("Platform {} is not supported.".format(system))
        for disk_location in paths:
            args = cmd + [disk_location]
            try:
                subprocess.check_call(args)
            except Exception as error:
                cmdline = subprocess.list2cmdline(args)
                self.logger.exception("Failed to launch {}!".format(cmdline))

    def _export_mel(self):
        """
        Exports Mel file from 3de4 to maya 
        """
        import os
        import sgtk
        from sgtk.util.filesystem import ensure_folder_exists

        # from .camera import TDECamera
        # from .lens import TDELens
        # from .point_group import TDEPointGroup
        import builtins as builtin
        import tde4
        from export_maya import _maya_export_mel_file


        # _export_requester_maya	= tde4.createCustomRequester()
        # req	 = _export_requester_maya
        # tde4.addFileWidget(req,"file_browser","Exportfile...","*.mel")
        # tde4.addTextFieldWidget(req, "startframe_field", "Startframe", "1")
        # tde4.addOptionMenuWidget(req,"camera_selection","Export", "Current Camera Only", "Selected Cameras Only", "Sequence Cameras Only", "Reference Cameras Only","All Cameras")
        # tde4.setWidgetValue(req,"camera_selection","5")
        # tde4.addToggleWidget(req,"hide_ref_frames","Hide Reference Frames",0)
        # tde4.addOptionMenuWidget(req,"model_selection","Export", "No 3D Models At All", "Selected 3D Models Only","All 3D Models")
        # tde4.setWidgetValue(req,"model_selection","3")
        # tde4.addToggleWidget(req,"export_texture","Export UV Textures",0)
        # tde4.addTextFieldWidget(req,"export_overscan_width_percent","Overscan Width %","100")
        # tde4.addTextFieldWidget(req,"export_overscan_height_percent","Overscan Height %","100")
        # tde4.setWidgetValue(req,"model_selection","1")
        # tde4.addOptionMenuWidget(req,"units","Units","cm", "m", "mm","in","ft","yd")

        #print(tde4.getWidgetValue(req,"camera_selection"))
        #print(tde4.getWidgetValue(req,"model_selection"))

        campg	= None
        pgl	= tde4.getPGroupList()
        for pg in pgl:
            if tde4.getPGroupType(pg)=="CAMERA": campg = pg
        # if campg==None:
        #     tde4.postQuestionRequester("Export Maya...","Error, there is no camera point group.","Ok")

        cam	= tde4.getCurrentCamera()
        offset	= tde4.getCameraFrameOffset(cam)
        startFrame = builtin.float(builtin.str(offset))
        #tde4.setWidgetValue(req,"startframe_field",builtin.str(offset))
        # ret	= tde4.postCustomRequester(req,"Export Maya (MEL-Script)...",700,0,"Ok","Cancel")

        #if ret==1:
        camera_selection = 5 #tde4.getWidgetValue(req,"camera_selection")
        model_selection = 1 #tde4.getWidgetValue(req,"model_selection")

        #print(builtin.float(tde4.getWidgetValue(req,"export_overscan_width_percent"))/100.0)

        overscan_w_pc = 1.0 #builtin.float(tde4.getWidgetValue(req,"export_overscan_width_percent"))/100.0
        overscan_h_pc = 1.0 #builtin.float(tde4.getWidgetValue(req,"export_overscan_height_percent"))/100.0
        export_material = 0 #tde4.getWidgetValue(req,"export_texture")
        camera_list = tde4.getCameraList()

        #1 : cm -> cm,2 : cm -> m, 3 : cm -> mm,4 : cm -> in,5 : cm -> ft,6 : cm -> yd
        unit_scales = {1 : 1.0,2 : 0.01,  3 : 10.0, 4 : 0.393701, 5 : 0.0328084, 6 : 0.0109361} 
        #print(unit_scales[tde4.getWidgetValue(req,"units")])
        unit_scale_factor = unit_scales[1.0]#unit_scales[tde4.getWidgetValue(req,"units")]

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

        path	= "/mnt/assets/katana_sg_dev/sequences/Jay_SEQ001/JY_SH001/MMV/work/maya_export/tst.mel" #tde4.getWidgetValue(req,"file_browser")
        frame0	= startFrame #builtin.float(tde4.getWidgetValue(req,"startframe_field"))
        frame0	-= 1
        #print(tde4.getWidgetValue(req,"hide_ref_frames"))
        hide_ref= 0 #tde4.getWidgetValue(req,"hide_ref_frames")
        
        _maya_export_mel_file(path,campg,camera_list,model_selection,overscan_w_pc,overscan_h_pc,export_material,unit_scale_factor,frame0,hide_ref)
        
        # # if ok==1:
        # #     tde4.postQuestionRequester("Export Maya...","Project successfully exported.","Ok")
        # # else:
        # #     tde4.postQuestionRequester("Export Maya...","Error, couldn't open file.","Ok")
        # import os
        # import sgtk
        # from sgtk.util.filesystem import ensure_folder_exists

        # # from .camera import TDECamera
        # # from .lens import TDELens
        # # from .point_group import TDEPointGroup
        # import builtins as builtin
        # import tde4
        # from export_maya import _maya_export_mel_file


        # _export_requester_maya	= tde4.createCustomRequester()
        # req	 = _export_requester_maya
        # tde4.addFileWidget(req,"file_browser","Exportfile...","*.mel")
        # tde4.addTextFieldWidget(req, "startframe_field", "Startframe", "1")
        # tde4.addOptionMenuWidget(req,"camera_selection","Export", "Current Camera Only", "Selected Cameras Only", "Sequence Cameras Only", "Reference Cameras Only","All Cameras")
        # tde4.setWidgetValue(req,"camera_selection","5")
        # tde4.addToggleWidget(req,"hide_ref_frames","Hide Reference Frames",0)
        # tde4.addOptionMenuWidget(req,"model_selection","Export", "No 3D Models At All", "Selected 3D Models Only","All 3D Models")
        # tde4.setWidgetValue(req,"model_selection","3")
        # tde4.addToggleWidget(req,"export_texture","Export UV Textures",0)
        # tde4.addTextFieldWidget(req,"export_overscan_width_percent","Overscan Width %","100")
        # tde4.addTextFieldWidget(req,"export_overscan_height_percent","Overscan Height %","100")
        # tde4.setWidgetValue(req,"model_selection","1")
        # tde4.addOptionMenuWidget(req,"units","Units","cm", "m", "mm","in","ft","yd")

        # campg	= None
        # pgl	= tde4.getPGroupList()
        # for pg in pgl:
        #     if tde4.getPGroupType(pg)=="CAMERA": campg = pg
        # if campg==None:
        #     tde4.postQuestionRequester("Export Maya...","Error, there is no camera point group.","Ok")

        # cam	= tde4.getCurrentCamera()
        # offset	= tde4.getCameraFrameOffset(cam)
        # tde4.setWidgetValue(req,"startframe_field",builtin.str(offset))
        # ret	= tde4.postCustomRequester(req,"Export Maya (MEL-Script)...",700,0,"Ok","Cancel")

        # if ret==1:
        #     camera_selection = tde4.getWidgetValue(req,"camera_selection")
        #     model_selection = tde4.getWidgetValue(req,"model_selection")

        #     overscan_w_pc = builtin.float(tde4.getWidgetValue(req,"export_overscan_width_percent"))/100.0
        #     overscan_h_pc = builtin.float(tde4.getWidgetValue(req,"export_overscan_height_percent"))/100.0
        #     export_material = tde4.getWidgetValue(req,"export_texture")
        #     camera_list = tde4.getCameraList()

        #     #1 : cm -> cm,2 : cm -> m, 3 : cm -> mm,4 : cm -> in,5 : cm -> ft,6 : cm -> yd
        #     unit_scales = {1 : 1.0,2 : 0.01,  3 : 10.0, 4 : 0.393701, 5 : 0.0328084, 6 : 0.0109361} 
        #     unit_scale_factor = unit_scales[tde4.getWidgetValue(req,"units")]

        #     if camera_selection == 1:
        #         camera_list = [tde4.getCurrentCamera()]
        #     elif camera_selection == 2:
        #         camera_list = tde4.getCameraList(1)
        #     elif camera_selection == 3:
        #         camera_list = []
        #         tcl =  tde4.getCameraList()
        #         for c in tcl:
        #             if tde4.getCameraType(c) == "SEQUENCE":
        #                 camera_list.append(c)
        #     elif camera_selection == 4:
        #         camera_list = []
        #         tcl =  tde4.getCameraList()
        #         for c in tcl:
        #             if tde4.getCameraType(c) == "REF_FRAME":
        #                 camera_list.append(c)

        #     path	= tde4.getWidgetValue(req,"file_browser")
        #     frame0	= builtin.float(tde4.getWidgetValue(req,"startframe_field"))
        #     frame0	-= 1
        #     hide_ref= tde4.getWidgetValue(req,"hide_ref_frames")
            
        #     ok	= _maya_export_mel_file(path,campg,camera_list,model_selection,overscan_w_pc,overscan_h_pc,export_material,unit_scale_factor,frame0,hide_ref)
            
        #     if ok==1:
        #         tde4.postQuestionRequester("Export Maya...","Project successfully exported.","Ok")
        #     else:
        #         tde4.postQuestionRequester("Export Maya...","Error, couldn't open file.","Ok")

    def _cleanup_folders(self):
        """
        Clean up the menu folders for the engine.
        """
        custom_scripts_dir_path = os.environ["TK_3DE4_MENU_DIR"]
        if os.path.isdir(custom_scripts_dir_path):
            shutil.rmtree(custom_scripts_dir_path)
