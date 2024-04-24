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
sys.path.append(os.path.join(os.path.abspath("."), "ui"))
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog
from PyQt5.QtMultimedia import QSound
from ui.ui_screen_tips import Ui_Dota2ScreenTipsDlg
from ui.ui_screen_tips_ctrl import Ui_Dota2ScreenTipsCtrlDlg
import ui.img_group_rc
import numpy
import pyautogui
from PIL import Image
from paddleocr import PaddleOCR
import paddle


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
        (2,30,"神符"),
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
        self.do_updata_gametime_timer()


    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground)  # 窗体背景透明
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # 点击穿透
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)  # 窗口置顶，无边框，在任务栏不显示图标
        self.move(0,0)


    def show_controllor(self):
        self.ctrlWnd = Dota2ScreenTipsCtrlPage(self)
        self.updata_gametime_signal.connect(self.do_updata_gametime_timer)
        self.close_tips_signal.connect(self.do_close_tips)
        self.roshan_countdown_signal.connect(self.record_roshan_dead_time)
        self.clear_countdown_signal.connect(self.clear_roshan_text)
        self.start_1esc_timer_signal.connect(self.start_1sec_timer)
        self.pause_1esc_timer_signal.connect(self.pause_1sec_timer)
        self.ctrlWnd.show()


    def set_timers(self):
        self.min = 0
        self.sec = 0

        self.rt_deltaTime = 1000
        self.timer_1sec = QTimer()
        self.timer_1sec.timeout.connect(self.running_time_timer_timeout)
        self.timer_1sec.start(self.rt_deltaTime)


    def do_updata_gametime_timer(self):
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
        else:
            if min % 10 >= 5: 
                if min % 10 == 5 and sec <= 12:
                    text = "↖ <<< 肉山"
            elif min % 10 < 5: 
                if min % 10 == 0 and sec <= 12:
                    text = "肉山 >>> ↘"
            
        self.Text_Line_2.setText(text)

    

    def clear_roshan_text(self):
        text = ""
        self.is_countdown_start = False
        self.Text_Line_2.setText(text)


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
        pass


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


class Dota2ScreenTipsCtrlPage(QDialog, Ui_Dota2ScreenTipsCtrlDlg):
    def __init__(self, HomePageWnd, parent=None):
        super(Dota2ScreenTipsCtrlPage, self).__init__(parent)
        self.homepage = HomePageWnd
        self.setupUi(self)
        self.initUI()


    def initUI(self):
        self.setAttribute(Qt.WA_TranslucentBackground)  # 窗体背景透明
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)  # 窗口置顶，无边框, 不显示任务栏图标
        self.move(250, 10)
        self.btn_updataGameTime.clicked.connect(self.do_updata_gametime_btn_clicked)
        self.btn_close_tips.clicked.connect(self.do_close_tips_btn_clicked)
        self.btn_roshan_countdown.clicked.connect(self.do_roshan_countdown_btn_clicked)
        self.btn_clear_countdown.clicked.connect(self.do_clear_countdown_btn_clicked)
        self.btn_pauseGameTime.clicked.connect(self.do_pause_game_time_btn_clicked)


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


    def get_time_text(self, target_correct_rate = 0.8):
        from_region = (1245,30,75,20)
        res_text_list = self.get_ocr_img_text(from_region)
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


    def update_game_time(self):
        self.homepage.start_1esc_timer_signal.emit()
        start_time = time.time()
        OCRRes, time_min, time_sec = self.get_time_text()
        end_time = time.time()
        if OCRRes: 
            self.time_min = time_min
            time_sec = time_sec + int(end_time - start_time)
            self.time_sec = time_sec
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


app = QApplication(sys.argv)
Wnd = Dota2ScreenTipsHomePage()
Wnd.show()
app.exec_()