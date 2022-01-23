from datetime import datetime
import threading
import json
import os
import shutil
import sys
import hashlib

import pysvn
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (QApplication, QTableWidget, QTableWidgetItem,
                               QWidget)


__path__ = os.path.dirname(os.path.realpath(__file__))

client = pysvn.Client()
# changes = client.status
# for change in changes:
#     print(change,change.text_status)


class Setting(object):

    class Data():
        username = None
        password = None
        workdir = None

    def __init__(self):
        super(Setting, self).__init__()
        with open("setting\setting.json", "r", encoding="utf-8") as f:
            settingfile = json.load(f)
        self.Data.username = settingfile["UserName"]
        self.Data.password = settingfile["Password"]
        self.Data.workdir = settingfile["WorkDir"]


class WindowData(object):
    main = None


class WindowModule(object):
    class Main(QWidget):
        def __init__(self, parent=None):
            super(WindowModule.Main, self).__init__(parent)
            self.ui = None
            self.build_ui()  # 初始化UI
            self.set_style()
            self.write_data()  # 从设置文件中写入控件内容

        def build_ui(self):
            ui = "%s/ui/main_window.ui" % __path__
            self.ui = QUiLoader().load(ui, parentWidget=None)

        def set_style(self):
            self.ui.changeList.setColumnWidth(0, 200)
            self.ui.changeList.setColumnWidth(2, 200)

        def write_data(self):
            pass


class WindowController(object):
    class Main(object):
        def __init__(self):
            ctr = WindowController.Main
            ui = WindowData.main.ui
            ui.findChanges.clicked.connect(ctr.on_findChanges_clicked)
            ui.commitBtn.clicked.connect(ctr.on_commitBtn_clicked)

        @staticmethod
        def on_findChanges_clicked():
            ui = WindowData.main.ui
            changelist: QTableWidget = ui.changeList
            # 清空rows
            changelist.setRowCount(0)
            changelist.setRowCount(1)
            empitem = QTableWidgetItem("——————未发现任何修改")
            changelist.setItem(0, 0, empitem)
            # 获取更改
            changes = ScriptManager.find_changes()
            ScriptManager.list_all_changes(changes)

        @staticmethod
        def on_commitBtn_clicked():
            ScriptManager.commit_changes()


class ScriptManager():

    @staticmethod
    def list_all_changes(changes):
        ui = WindowData.main.ui
        changelist: QTableWidget = ui.changeList

        r = 0

        for c_path, c_props in changes.items():
            c_st = c_props["status"]
            c_target = c_props["target_path"]
            c_target_st = c_props["target_status"]
            c_target_log = c_props["log"]

            # get color
            c_brush = ScriptManager.get_change_color(c_st)
            t_brush = ScriptManager.get_change_color(c_target_st)

            # changed item's path
            ichange = QTableWidgetItem()
            ichange.setText(c_path)
            ichange.setCheckState(Qt.Checked)
            ichange.setForeground(c_brush)

            # changed item's type
            itype = QTableWidgetItem()
            itype.setText(c_st)
            itype.setForeground(c_brush)

            # changed item's target
            itarget = QTableWidgetItem()
            itarget.setText(c_target)
            itarget.setForeground(t_brush)

            # target status of changed item
            itarget_st = QTableWidgetItem()
            itarget_st.setText(c_target_st)
            itarget_st.setForeground(t_brush)

            # target logs
            itarget_log = QTableWidgetItem()
            itarget_log.setText(c_target_log)
            itarget_log.setForeground(t_brush)

            # write changeList
            changelist.setRowCount(r+1)
            changelist.setItem(r, 0, ichange)
            changelist.setItem(r, 1, itype)
            changelist.setItem(r, 2, itarget)
            changelist.setItem(r, 3, itarget_st)
            changelist.setItem(r, 4, itarget_log)
            r += 1

    @staticmethod
    def find_changes():
        workdir: dict = Setting.Data.workdir
        changes = {}
        client = pysvn.Client()
        for trunk, target in workdir.items():

            trunk = trunk.replace("/", "\\")
            target = target.replace("/", "\\")

            all_item_status = client.status(trunk)

            for file_status in all_item_status:
                text_status = file_status.text_status
                if text_status == pysvn.pysvn.wc_status_kind.normal:
                    continue

                # trunk file path
                trunk_fp = file_status.path.replace("/", "\\")

                # init file property
                file_prop = {}
                trans_text = ScriptManager.translate_change_type(text_status)
                file_prop["status"] = trans_text

                # get target file path
                target_fp = trunk_fp.replace(trunk, target)
                file_prop["target_path"] = target_fp

                # get target file pathtype
                if os.path.exists(target_fp):
                    target_status = client.status(target_fp)[0].text_status
                    file_prop["target_status"] = ScriptManager.translate_change_type(
                        target_status)
                else:
                    file_prop["target_status"] = "不存在"
                    file_prop["log"] = ""

                # target log
                if file_prop["target_status"] not in ["无版本控制", "已忽略", "未分类", "不存在"]:
                    target_log = client.log(target_fp, limit=1)
                    author = target_log[0]["author"]
                    last_time = target_log[0]["date"]
                    last_time = datetime.fromtimestamp(
                        last_time).strftime("%Y-%m-%d %H:%M:%S")
                    log_message = target_log[0]["message"]
                    file_prop["log"] = f"{last_time}由{author}：{log_message}"
                else:
                    file_prop["log"] = ""

                # make dict
                changes[trunk_fp] = file_prop
        return changes
        # print(changes)

    @staticmethod
    def find_changes2():
        workdir: dict = Setting.Data.workdir
        changes = {}
        client = pysvn.Client()
        md5 = ScriptManager.get_file_md5
        # TODO 验证workdir是否存在于目录中
        for trunk_dir, target_dir in workdir.items():

            trunk_dir = trunk_dir.replace("/", "\\")
            target_dir = target_dir.replace("/", "\\")

            trunk_status: list = client.status(trunk_dir)
            # trunk_status.pop(0)

            for status in trunk_status:
                # 工作文件
                file_path: str = status.path
                text_status = status.text_status
                
                # 目录类
                if os.path.isdir(file_path):
                    pass # TODO 目录类型处理
                
                # 文件类
                else:
                    # 获取目标文件
                    target_file_path = file_path.replace(trunk_dir, target_dir)
                    # 目标文件存在
                    if os.path.exists(target_file_path):
                        print(target_file_path, ":", "存在")
                        # 对比MD5
                        file_md5 = md5(file_path)
                        print(file_md5)
                        target_file_md5 = md5(target_file_path)
                        print(target_file_md5)
                        if file_md5 == target_file_md5:
                            # 一样的不用管
                            print("这俩一样")
                            continue
                    # 不存在
                    else:
                        print(target_file_path, ":", "不存在")
                        
                file_prop = {}
                file_prop["file_name"] = file_name
                file_prop["trunk"] = trunk_dir
                file_prop["trunk_status"] = file_status_trans
                file_prop["target"] = target_dir
                file_prop["target_status"] = tfile_status_trans
                file_prop["sync_status"]
                file_prop["log"]

        pass

    @staticmethod
    def get_file_md5(file_path):
        if not os.path.exists(file_path):
            return
        if os.path.isdir(file_path):
            return
        f = open(file_path, 'rb')
        md5_obj = hashlib.md5()
        while True:
            d = f.read(8096)
            if not d:
                break
            md5_obj.update(d)
        hash_code = md5_obj.hexdigest()
        f.close()
        md5 = str(hash_code).lower()
        return md5

    @staticmethod
    def translate_change_type(change_type):
        pywc = pysvn.wc_status_kind
        if change_type == pywc.modified:
            return "修改"
        elif change_type == pywc.normal:
            return "正常"
        elif change_type == pywc.unversioned:
            return "无版本控制"
        elif change_type == pywc.missing:
            return "缺少"
        elif change_type == pywc.added:
            return "已增加"
        elif change_type == pywc.deleted:
            return "删除"
        elif change_type == pywc.ignored:
            return "已忽略"
        else:
            return "未分类"

    @staticmethod
    def get_change_color(change_type):
        if change_type == "修改":
            color = QColor(0, 50, 160)
        elif change_type == "无版本控制":
            color = QColor(0, 0, 0)
        elif change_type == "缺少":
            color = QColor(100, 50, 100)
        elif change_type == "已增加":
            color = QColor(100, 0, 100)
        elif change_type == "删除":
            color = QColor(100, 0, 0)
        elif change_type == "已忽略":
            color = QColor(0, 0, 0)
        else:
            color = QColor(0, 0, 0)
        brush = QBrush(color)
        return brush

    @staticmethod
    def commit_changes():
        ui = WindowData.main.ui
        tablist: QTableWidget = ui.changeList

        all_row = tablist.rowCount()

        pending_files = ""
        for row in range(0, all_row):
            trunk_path = tablist.item(row, 0)
            trunk_type = tablist.item(row, 1)
            target_path = tablist.item(row, 2)

            if trunk_path.checkState() != Qt.Checked:
                continue

            work_file = trunk_path.text()
            pending_files += "*"+work_file

            target_file = target_path.text()
            pending_files += "*"+target_file

            if trunk_type.text() in ["缺少", "删除"]:
                if os.path.exists(target_file):
                    if os.path.isfile(target_file):
                        os.remove(target_file)
                    elif os.path.isdir(target_file):
                        os.rmdir(target_file)
            elif trunk_type.text() in ["修改", "无版本控制", "已增加"]:
                shutil.copy(work_file, target_file)
            else:
                pass

        t = SvnPro(pending_files)
        t.start()

    @staticmethod
    def call_svn_pro(work_path):
        os.system(
            f'"TortoiseProc" /command:commit /path:{work_path} /closeonend:3')


class SvnPro(threading.Thread):
    def __init__(self, work_path):
        super().__init__()
        self.work_path = work_path

    def run(self):
        os.system(
            f'"TortoiseProc" /command:commit /path:{self.work_path} /closeonend:3')


def create_window():

    app = QApplication(sys.argv)
    WindowData.main = WindowModule.Main()
    WindowController.Main()
    WindowData.main.ui.show()
    changes = ScriptManager.find_changes2()
    # ScriptManager.list_all_changes(changes)
    sys.exit(app.exec())


if __name__ == "__main__":
    Setting()
    create_window()
