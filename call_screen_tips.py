# 【完成】窗口置顶 & 启动后移动至固定位置 & 透明底 & 无边框 & 屏蔽点击和输入
# 每10秒检测Dota2进程的启动情况，未启动则等待下一轮检测，等待过程中显示检测情况
# 检测到启动后，每秒识别屏幕内特定区域的时间数字并显示，没有则不显示任何信息
# 【完成】识别过程记录前后延迟，并对显示的时间进行延迟修正
# 特定时间点播放语音，显示文本

import sys
import os
import time
import win32gui
import win32con
from ctypes import *
from ctypes.wintypes import *
import tkinter.messagebox
sys.path.append(os.path.join(os.path.abspath("."), "ui"))
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog
from PyQt5.QtMultimedia import QSound
from PyQt5.QtGui import QPainter, QPen
from ui.ui_screen_tips import Ui_Dota2ScreenTipsDlg
from ui.ui_screen_tips_1800_1200 import Ui_Dota2ScreenBigTipsDlg
from ui.ui_screen_tips_ctrl import Ui_Dota2ScreenTipsCtrlDlg
import numpy
import pyautogui
from paddleocr import PaddleOCR


p_cls_model =   r".paddleocr\whl\cls\ch_ppocr_mobile_v2.0_cls_infer"
p_cls_conf =    r".paddleocr\configs\cls\ch_PP-OCRv3\ch_PP-OCRv3_rotnet.yml"

p_det_model =   r".paddleocr\whl\det\en\en_PP-OCRv3_det_infer"
p_det_conf =    r".paddleocr\configs\det\ch_PP-OCRv3\ch_PP-OCRv3_det_student.yml"

p_rec_model =   r".paddleocr\whl\rec\en\en_PP-OCRv4_rec_infer"
p_rec_conf =    r".paddleocr\configs\rec\PP-OCRv4\en_PP-OCRv4_rec.yml"


class Dota2ScreenTipsHomePage(QMainWindow, Ui_Dota2ScreenTipsDlg):
    updata_gametime_signal = pyqtSignal()
    close_tips_signal = pyqtSignal()
    roshan_countdown_signal = pyqtSignal()
    clear_countdown_signal = pyqtSignal()
    pause_1esc_timer_signal = pyqtSignal()
    start_1esc_timer_signal = pyqtSignal()
    wav_wait_runes = r"wav\Notification_processed_73.wav"
    wav_refresh_runes = r"wav\Notification_processed_76.wav"
    wav_wait_roshan = r"wav\Notification_processed_74.wav"
    wav_rebirth_roshan = r"wav\Notification_processed_75.wav"
    wav_mons = r"wav\Notification_processed_71.wav"
    time_to_attention_runes = [
        (2,30,"状态符"),
        (3,30,"赏金&莲花"),
        (7,45,"经验符")
        ]
        # 参数：每N分钟提醒|提前M秒提醒|预告音频路径|触发音频路径|神符类型文本
    time_to_attention_refresh_mons = [53,20]            # 每分钟53秒时拉野|提前30秒出现提示
    rs_m = -1
    rs_s = -1
    is_countdown_start = False

    def __init__(self, parent=None):
        super(Dota2ScreenTipsHomePage, self).__init__(parent)
        self.setupUi(self)
        self.initUI()
        self.set_timers()
        self.show_controllor()
        self.show_tips_big()
        self.do_updata_gametime_timer()


    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground)  # 窗体背景透明
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # 点击穿透
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)  # 窗口置顶，无边框，在任务栏不显示图标
        self.move(int(2560 / 2 - 472 / 2 - 10), 70)
        self.showMinimized()


    def show_controllor(self):
        self.ctrlWnd = Dota2ScreenTipsCtrlPage(self)
        self.updata_gametime_signal.connect(self.do_updata_gametime_timer)
        self.close_tips_signal.connect(self.do_close_tips)
        self.roshan_countdown_signal.connect(self.record_roshan_dead_time)
        self.clear_countdown_signal.connect(self.clear_roshan_text)
        self.start_1esc_timer_signal.connect(self.start_1sec_timer)
        self.pause_1esc_timer_signal.connect(self.pause_1sec_timer)
        self.ctrlWnd.show()


    def show_tips_big(self):
        self.bigTipsWnd = Dota2ScreenTipsBigPage()
        self.bigTipsWnd.show()


    def set_timers(self):
        self.min = 0
        self.sec = 0

        self.rt_deltaTime = 1000
        self.timer_1sec = QTimer()
        self.timer_1sec.timeout.connect(self.running_time_timer_timeout)
        self.timer_1sec.start(self.rt_deltaTime)


    def do_updata_gametime_timer(self):
        # self.a = update_gametime_thread(self)
        # self.a.gt_update_signal.connect(self.update_time_text)
        # self.a.run()
        self.thread_gt_update = update_gametime_thread(self)
        self.thread_gt_update.gt_update_signal.connect(self.update_time_text)
        self.thread_gt_update.start()


    def do_close_tips(self):
        self.close()
        QApplication.instance().quit()


    def record_roshan_dead_time(self):
        self.is_countdown_start = True
        self.rs_m = self.min
        self.rs_s = self.sec


    def running_time_timer_timeout(self):
        self.thread_rt_update = running_time_update_thread(self.min, self.sec)
        self.thread_rt_update.rt_update_signal.connect(self.update_time_text)
        self.thread_rt_update.start()


    def update_time_text(self, min, sec):
        self.min = min
        self.sec = sec

        sec_text = ""
        if sec < 10:
            sec_text = "0" + str(sec)
        else:
            sec_text = str(sec)

        text = str(min) + ":" + sec_text
        self.Text_GameTime.setText(text)
        self.bigTipsWnd.Text_GameTime.setText(text)


        self.set_daynight_text_by_time(min, sec)
        self.set_mons_refresh_text_by_time(min, sec)
        self.set_runes_text_by_time(min, sec)
        self.set_roshan_text_by_time(min, sec)


    def play_wav(self, path):
        QSound.play(path)


    def pause_1sec_timer(self):
        self.timer_1sec.stop()


    def start_1sec_timer(self):
        if not self.timer_1sec.isActive():
            self.timer_1sec.start()


    def set_roshan_text_by_time(self, min, sec):
        text = ""
        if self.is_countdown_start:
            rebirth_sec = self.rs_s
            rebirth_min = self.rs_m + 8
            remind_sec = (rebirth_min * 60 + rebirth_sec) - (min * 60 + sec)
            remind_time_min = int(remind_sec / 60)
            remind_time_sec = remind_sec % 60
            remind_time_sec_text = ""

            if remind_time_sec < 10:
                remind_time_sec_text = "0" + str(remind_time_sec)
            else:
                remind_time_sec_text = str(remind_time_sec)
            if 60 * 3 < remind_sec and remind_sec <= 60 * 8:
                text = "肉山还有%i:%s刷新(盾剩余约%i秒)" % (remind_time_min, remind_time_sec_text, (remind_sec - 60 * 3))
            elif 60 <= remind_sec and remind_sec <= 60 * 3:
                text = "肉山还有%i:%s刷新" % (remind_time_min, remind_time_sec_text)
            elif 0 <= remind_sec and remind_sec < 60:
                tgt_road_text = "-"
                tgt_min = (self.rs_m + 8) % 10 
                if tgt_min >= 5:
                    tgt_road_text = "↖"
                else:
                    tgt_road_text = "↘"
                text = "肉山即将刷新-%i(%s)" % (remind_sec, tgt_road_text)
            elif -60 * 3 < remind_sec and remind_sec < 0:
                tgt_road_text = "-"
                if min % 10 >= 5:
                    tgt_road_text = "↖"
                else:
                    tgt_road_text = "↘"
                text = "(%i)肉山刷新(%s)" % (180 + remind_sec, tgt_road_text)
            if remind_sec in [182, 181, 60, 4, 3, 2, 1]:
                self.play_wav(self.wav_wait_roshan)
            elif remind_sec in [180, 0]:
                self.play_wav(self.wav_rebirth_roshan)
        # else:
        #     if min % 10 >= 5: 
        #         if min % 10 == 5 and sec <= 12:
        #             text = "↖ <<< 肉山"
        #     elif min % 10 < 5: 
        #         if min % 10 == 0 and sec <= 12:
        #             text = "肉山 >>> ↘"
        self.Text_Line_2.setText(text)
        self.bigTipsWnd.Text_Line_2.setText(text)

    

    def clear_roshan_text(self):
        text = ""
        self.is_countdown_start = False
        self.Text_Line_2.setText(text)
        self.bigTipsWnd.Text_Line_2.setText(text)


    def set_runes_text_by_time(self, min, sec):
        text = ""
        rem_sec = 60 - sec
        for tupleInfo in self.time_to_attention_runes:
            tgt_min = tupleInfo[0]
            wait_sec = tupleInfo[1]
            runes_type = tupleInfo[2]
            rem_min = min % tgt_min
            if rem_min == tgt_min - 1 and sec >= 60 - wait_sec:
                text += "【%s】" % (runes_type)
                if sec == 60 - wait_sec:
                    self.play_wav(self.wav_wait_runes)
                if sec >= 57:
                    self.play_wav(self.wav_wait_runes)
            elif rem_min == 0 and sec == 0:
                self.play_wav(self.wav_refresh_runes)
        if text != "":
            text += "%i秒 " % rem_sec
        self.Text_Line_4.setText(text)
        self.bigTipsWnd.Text_Line_4.setText(text)


    def set_daynight_text_by_time(self, min, sec):
        text = ""
        rem = min % 10

        sec_text = ""
        if 60-sec < 10:
            sec_text = "0" + str(60-sec)
        else:
            sec_text = str(60-sec)

        if rem >= 0 and rem < 5:
            text = "%i:%s后夜晚" % (5-rem-1, sec_text) 
        else:
            text = "%i:%s后白天" % (10-rem-1, sec_text) 
        self.Text_Line_1.setText(text)
        self.bigTipsWnd.Text_Line_1.setText(text)


    def set_mons_refresh_text_by_time(self, min, sec):
        if min > 15:
            return
        
        refresh_sec = self.time_to_attention_refresh_mons[0]
        wait2refresh_sec = self.time_to_attention_refresh_mons[1]
        text = ""
        
        if sec >= refresh_sec - wait2refresh_sec and sec < refresh_sec:
            text = "前往拉野(%i)" % (refresh_sec - sec)
            if sec == refresh_sec - wait2refresh_sec:
                self.play_wav(self.wav_mons)
        self.Text_Line_3.setText(text)
        self.bigTipsWnd.Text_Line_3.setText(text)


class HotKey(QThread):
    signal_hotkey_press = pyqtSignal(int)
    vk_codes= {
        'a':0x41,
        'b':0x42,
        'c':0x43,
        'd':0x44,
        'e':0x45,
        'f':0x46,
        'g':0x47,
        'h':0x48,
        'i':0x49,
        'j':0x4A,
        'k':0x4B,
        'l':0x4C,
        'm':0x4D,
        'n':0x4E,
        'o':0x5F,
        'p':0x50,
        'q':0x51,
        'r':0x52,
        's':0x53,
        't':0x54,
        'u':0x55,
        'v':0x56,
        'w':0x57,
        'x':0x58,
        'y':0x59,
        'z':0x5A,
        '0':0x30,
        '1':0x31,
        '2':0x32,
        '3':0x33,
        '4':0x34,
        '5':0x35,
        '6':0x36,
        '7':0x37,
        '8':0x38,
        '9':0x39,
        "up": win32con.VK_UP
        , "kp_up": win32con.VK_UP
        , "down": win32con.VK_DOWN
        , "kp_down": win32con.VK_DOWN
        , "left": win32con.VK_LEFT
        , "kp_left": win32con.VK_LEFT
        , "right": win32con.VK_RIGHT
        , "kp_right": win32con.VK_RIGHT
        , "prior": win32con.VK_PRIOR
        , "kp_prior": win32con.VK_PRIOR
        , "next": win32con.VK_NEXT
        , "kp_next": win32con.VK_NEXT
        , "home": win32con.VK_HOME
        , "kp_home": win32con.VK_HOME
        , "end": win32con.VK_END
        , "kp_end": win32con.VK_END
        , "insert": win32con.VK_INSERT
        , "return": win32con.VK_RETURN
        , "tab": win32con.VK_TAB
        , "space": win32con.VK_SPACE
        , "backspace": win32con.VK_BACK
        , "delete": win32con.VK_DELETE
        , "escape": win32con.VK_ESCAPE , "pause": win32con.VK_PAUSE
        , "kp_multiply": win32con.VK_MULTIPLY
        , "kp_add": win32con.VK_ADD
        , "kp_separator": win32con.VK_SEPARATOR
        , "kp_subtract": win32con.VK_SUBTRACT
        , "kp_decimal": win32con.VK_DECIMAL
        , "kp_divide": win32con.VK_DIVIDE
        , "kp_0": win32con.VK_NUMPAD0
        , "kp_1": win32con.VK_NUMPAD1
        , "kp_2": win32con.VK_NUMPAD2
        , "kp_3": win32con.VK_NUMPAD3
        , "kp_4": win32con.VK_NUMPAD4
        , "kp_5": win32con.VK_NUMPAD5
        , "kp_6": win32con.VK_NUMPAD6
        , "kp_7": win32con.VK_NUMPAD7
        , "kp_8": win32con.VK_NUMPAD8
        , "kp_9": win32con.VK_NUMPAD9
        , "f1": win32con.VK_F1
        , "f2": win32con.VK_F2
        , "f3": win32con.VK_F3
        , "f4": win32con.VK_F4
        , "f5": win32con.VK_F5
        , "f6": win32con.VK_F6
        , "f7": win32con.VK_F7
        , "f8": win32con.VK_F8
        , "f9": win32con.VK_F9
        , "f10": win32con.VK_F10
        , "f11": win32con.VK_F11
        , "f12": win32con.VK_F12
        , "f13": win32con.VK_F13
        , "f14": win32con.VK_F14
        , "f15": win32con.VK_F15
        , "f16": win32con.VK_F16
        , "f17": win32con.VK_F17
        , "f18": win32con.VK_F18
        , "f19": win32con.VK_F19
        , "f20": win32con.VK_F20
        , "f21": win32con.VK_F21
        , "f22": win32con.VK_F22
        , "f23": win32con.VK_F23
        , "f24": win32con.VK_F24
        }
    win_modders = {
        "shift": win32con.MOD_SHIFT
        ,"control": win32con.MOD_CONTROL
        ,"alt": win32con.MOD_ALT
        ,"super": win32con.MOD_WIN
        }
    def __init__(self, key_str):
        super(HotKey, self).__init__()
        self.main_key = self.get_code_by_key(key_str)

    def get_code_by_key(self, find_this_key_str):
        if find_this_key_str in self.vk_codes.keys():
            return self.vk_codes[find_this_key_str]
        else:
            return None
        
    
    def run(self):
        if self.main_key == None:
            return
        
        user32 = windll.user32
        while True:
            if not user32.RegisterHotKey(None, 1, win32con.MOD_CONTROL, self.main_key):
                tkinter.messagebox.showerror("错误","全局热键注册失败。")
            try:
                msg = MSG()
                if user32.GetMessageA(byref(msg), None, 0, 0) != 0:
                    if msg.message == win32con.WM_HOTKEY:
                        if msg.wParam == win32con.MOD_ALT:
                            self.signal_hotkey_press.emit(msg.lParam)
            finally:
                user32.UnregisterHotKey(None, 1)


class Dota2ScreenTipsCtrlPage(QDialog, Ui_Dota2ScreenTipsCtrlDlg):
    ctrl_sound_cencel_path = r"wav\Sequenced_32.wav"
    ctrl_sound_clicked_path = r"wav\Clicks.wav"
    updata_cooldown_timer = QTimer()
    is_updata_cooldown = False
    def __init__(self, HomePageWnd, parent=None):
        super(Dota2ScreenTipsCtrlPage, self).__init__(parent)
        self.homepage = HomePageWnd
        self.setupUi(self)
        self.initUI()
        self.initShortCut()
        QSound.play(self.ctrl_sound_clicked_path)


    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground)  # 窗体背景透明
        self.setWindowFlags(Qt.FramelessWindowHint)  # Qt.WindowStaysOnTopHint | 窗口置顶，无边框, 不显示任务栏图标 | Qt.FramelessWindowHint | Qt.Tool
        self.setGeometry(self.get_subscreen_available_rect())
        self.showMaximized()
        self.btn_updataGameTime.clicked.connect(self.do_updata_gametime_btn_clicked)
        self.btn_close_tips.clicked.connect(self.do_close_tips_btn_clicked)
        self.btn_roshan_countdown.clicked.connect(self.do_roshan_countdown_btn_clicked)
        self.btn_clear_countdown.clicked.connect(self.do_clear_countdown_btn_clicked)
        self.btn_pauseGameTime.clicked.connect(self.do_pause_game_time_btn_clicked)


    def initShortCut(self):
        self.hk_roshan_timer_start, self.hk_roshan_timer_clear = HotKey('kp_0'), HotKey('kp_decimal')
        self.hk_game_timer_updata, self.hk_game_timer_pause = HotKey('kp_add'), HotKey('kp_subtract')
        self.updata_cooldown_timer.timeout.connect(self.updata_cooldown_over)

        self.hk_roshan_timer_start.signal_hotkey_press.connect(lambda: self.press_key_event(1))
        self.hk_roshan_timer_start.start()
        self.hk_roshan_timer_clear.signal_hotkey_press.connect(lambda: self.press_key_event(2))
        self.hk_roshan_timer_clear.start()
        self.hk_game_timer_updata.signal_hotkey_press.connect(lambda: self.press_key_event(3))
        self.hk_game_timer_updata.start()
        self.hk_game_timer_pause.signal_hotkey_press.connect(lambda: self.press_key_event(4))
        self.hk_game_timer_pause.start()


    def updata_cooldown_over(self):
        self.is_updata_cooldown = False


    def press_key_event(self, code:int):
        if code == 1:
            self.do_roshan_countdown_btn_clicked()
            QSound.play(self.ctrl_sound_clicked_path)
        elif code == 2:
            self.do_clear_countdown_btn_clicked()
        elif code == 3:
            if not self.is_updata_cooldown:              
                self.do_updata_gametime_btn_clicked()
                QSound.play(self.ctrl_sound_clicked_path)
                self.is_updata_cooldown = True
                self.updata_cooldown_timer.start(5000)
        elif code == 4:
            self.do_pause_game_time_btn_clicked()
            QSound.play(self.ctrl_sound_cencel_path)


    def get_subscreen_available_rect(self):
        primary_screen = QApplication.primaryScreen()
        screens = QApplication.screens()
        for screen in screens:
            if not screen is primary_screen:
                auxiliary_screen = screen
                break
            else:
                auxiliary_screen = None
        primary_rect = primary_screen.geometry()
        primary_available_rect = primary_screen.availableGeometry()
        screen_2_rect = auxiliary_screen.geometry()
        screen_2_available_rect = auxiliary_screen.availableGeometry()

        return screen_2_available_rect

        

    def do_updata_gametime_btn_clicked(self):
        self.homepage.updata_gametime_signal.emit()
        self.focus_to_dota2()


    def do_close_tips_btn_clicked(self):
        self.homepage.close_tips_signal.emit()
        self.close()


    def do_roshan_countdown_btn_clicked(self):
        self.homepage.roshan_countdown_signal.emit()
        self.focus_to_dota2()


    def do_clear_countdown_btn_clicked(self):
        self.homepage.clear_countdown_signal.emit()
        self.focus_to_dota2()


    def do_pause_game_time_btn_clicked(self):
        self.homepage.pause_1esc_timer_signal.emit()
        self.focus_to_dota2()


    def focus_to_dota2(self):
        hwnd = win32gui.FindWindow(None, 'Dota 2')
        if hwnd:
            win32gui.BringWindowToTop(hwnd)


class update_gametime_thread(QThread):
    gt_update_signal = pyqtSignal(int, int)
    def __init__(self, homepage, parent=None):
        super().__init__(parent)
        self.homepage = homepage
        self.time_min = 0
        self.time_sec = 0
       

    def run(self) -> None:
        self.update_game_time()


    def get_ocr_img_text(self, from_region = (0,0,10,10)):
        image = pyautogui.screenshot(region = from_region)  # 使用pyautogui进行截图操作
        image = numpy.array(image)
        ocr = PaddleOCR(
            use_angle_cls=False, lang="en", use_gpu=False,
            cls_model_dir=p_cls_model, det_model_dir=p_det_model, rec_model_dir=p_rec_model,
            cls_config=p_cls_conf, det_config=p_det_conf, rec_config=p_rec_conf
            )
        result = ocr.ocr(image, cls=True)
        res_text_list = []
        for line in result:
            if line == None:
                continue
            line_res = line[0][1]
            res_text_list.append(line_res)
        return res_text_list


    def get_time_text(self, target_correct_rate = 0.6):
        from_region = (1240,24,75,16)
        self.paint_ocr_rect(QRect(1235,24,75,17))
        res_text_list = self.get_ocr_img_text(from_region)
        print(res_text_list)
        if len(res_text_list) > 0:
            time_text = res_text_list[0][0]
            correct_rate = res_text_list[0][1]
            if correct_rate < target_correct_rate:
                return False, -1, -1
            if not ":" in time_text:
                return False, -1, -1
            time_min_text:str = time_text.split(":")[0]
            time_sec_text:str = time_text.split(":")[-1]
            if not (time_min_text.isdigit() and time_sec_text.isdigit()):
                return False, -1, -1
            time_min = int(time_min_text)
            time_sec = int(time_sec_text)
            return True, time_min, time_sec
        return False, -1, -1


    def paint_ocr_rect(self, rect):
        painter = QPainter()
        pen = QPen(Qt.red, 5)
        painter.setPen(pen)
        painter.drawRect(rect)


    def update_game_time(self):
        self.homepage.start_1esc_timer_signal.emit()
        start_time = time.time()
        OCRRes, time_min, time_sec = self.get_time_text()
        end_time = time.time()
        if OCRRes: 
            self.time_min = time_min
            self.time_sec = time_sec + int(end_time - start_time)
            self.gt_update_signal.emit(self.time_min, self.time_sec)


class running_time_update_thread(QThread):
    rt_update_signal = pyqtSignal(int, int)
    def __init__(self, min, sec):
        super(running_time_update_thread, self).__init__()
        self.time_min = min
        self.time_sec = sec


    def run(self) -> None:
        self.update_1sec()


    def update_1sec(self):
        self.time_sec += 1
        if self.time_sec >= 60:
            self.time_sec = 0
            self.time_min += 1
        self.rt_update_signal.emit(self.time_min, self.time_sec)


class Dota2ScreenTipsBigPage(QDialog, Ui_Dota2ScreenBigTipsDlg):
    close_big_tips_signal = pyqtSignal()
    big_tip_update_text_signal = pyqtSignal(str, str, str, str, str)
    def __init__(self, parent=None):
        super(Dota2ScreenTipsBigPage, self).__init__(parent)
        self.setupUi(self)
        self.initUI()


    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground)  # 窗体背景透明
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)  #无边框, 不显示任务栏图标
        self.setGeometry(self.get_subscreen_available_rect())
        self.showMaximized()
        self.close_big_tips_signal.connect(self.do_close_tips)


    def get_subscreen_available_rect(self):
        primary_screen = QApplication.primaryScreen()
        screens = QApplication.screens()
        if len(screens) < 3:
            primary_screen_rect = primary_screen.availableGeometry()
            self.do_close_tips()
            return primary_screen_rect
        auxiliary_screen = screens[2]
        screen_3_rect = auxiliary_screen.geometry()
        screen_3_available_rect = auxiliary_screen.availableGeometry()

        return screen_3_available_rect
    

    def do_close_tips(self):
        self.close()
        QApplication.instance().quit()


app = QApplication(sys.argv)
Wnd = Dota2ScreenTipsHomePage()
Wnd.show()
app.exec_()