# By Sam Saxon sam.saxon@thefoundry.com
# Copied from the equivalent Nuke file.

import os
import sgtk
from sgtk.platform.qt import QtGui
import tde4
import sgtk
HookClass = sgtk.get_hook_baseclass()


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(self, operation, file_path, context, parent_action, file_version, read_only, **kwargs):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """
        
        if operation == "current_path":
            # return the current scene path
            return file_path
            
        elif operation == "open":
            dirty = 0
            if not tde4.isProjectUpToDate():
                dirty = 1
            else:
                dirty = 0
            while dirty==1:
                res = QtGui.QMessageBox.question(None,
                                                 "Save your scene?",
                                                 "Your scene has unsaved changes. Save before proceeding?",
                                                 QtGui.QMessageBox.Yes|QtGui.QMessageBox.No|QtGui.QMessageBox.Cancel)
            
                if res == QtGui.QMessageBox.Cancel:
                    return False
                elif res == QtGui.QMessageBox.No:
                    break
                else:
                    tde4.saveProject(file_path)
                    dirty = 0
            tde4.loadProject(file_path)

        elif operation == "save":
            if not os.path.exists(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            tde4.saveProject(file_path)

        elif operation == "save_as":
            if not os.path.exists(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            tde4.saveProject(file_path)

        elif operation == "prepare_new":
            tde4.newProject()
            return True

        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            dirty = 0
            if not tde4.isProjectUpToDate():
                dirty = 1
            else:
                dirty = 0
            while dirty==1:
                res = QtGui.QMessageBox.question(None,
                                                 "Save your scene?",
                                                 "Your scene has unsaved changes. Save before proceeding?",
                                                 QtGui.QMessageBox.Yes|QtGui.QMessageBox.No|QtGui.QMessageBox.Cancel)
            
                if res == QtGui.QMessageBox.Cancel:
                    return False
                elif res == QtGui.QMessageBox.No:
                    break
                else:
                    tde4.saveProject(file_path)
                    dirty = 0

            # do new file:
            tde4.newProject()
            return True

        # elif operation == "reset":
        #     if not tde4.isProjectUpToDate():
        #         res = QtGui.QMessageBox.question(None,
        #                                          "Save your scene?",
        #                                          "Your scene has unsaved changes. Save before proceeding?",
        #                                          QtGui.QMessageBox.Yes|QtGui.QMessageBox.No|QtGui.QMessageBox.Cancel)
            
        #         if res == QtGui.QMessageBox.Cancel:
        #             return False
        #         elif res == QtGui.QMessageBox.No:
        #             break
        #         else:
        #             if not os.path.exists(os.path.dirname(path)):
        #                 os.makedirs(os.path.dirname(path))
        #         tde4.saveProject(path)
        #     return True

    # def _session_path():
    #     path = tde4.getProjectPath()
    #     if isinstance(path, bytes):
    #         path = path.decode('UTF-8')
            
    #     return path