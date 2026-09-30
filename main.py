import flet as ft
import requests
import json
import time
import random
import threading
from datetime import datetime, timedelta

FIREBASE_BASE_URL = "https://primeatm1-default-rtdb.asia-southeast1.firebasedatabase.app/"

current_user = None
selected_atm = None
user_atms = {}
generated_otp = None
current_session_id = 0  # નવો સેશન ID (Auto-Refresh માટે)

def fb_get(endpoint):
    try:
        r = requests.get(f"{FIREBASE_BASE_URL}{endpoint}.json", timeout=4)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def fb_put(endpoint, data):
    try:
        requests.put(f"{FIREBASE_BASE_URL}{endpoint}.json", json=data, timeout=4)
        return True
    except:
        return False

def main(page: ft.Page):
    global current_user, selected_atm, user_atms, generated_otp

    page.title = "Zevia PureX - Water ATM"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    if hasattr(page, "window"):
        page.window.width = 390
        page.window.height = 740
        page.window.resizable = False
    else:
        page.window_width = 390
        page.window_height = 740
        page.window_resizable = False

    def show_snack(text, color="green"):
        snack = ft.SnackBar(ft.Text(text, color="white", size=13), bgcolor=color, open=True)
        page.overlay.append(snack)
        page.update()

    def render_screen(content_widget):
        page.controls.clear()
        mobile_shell = ft.Container(
            content=content_widget,
            width=360,
            height=700,
            bgcolor="#111418",
            border_radius=15,
            padding=10,
        )
        wrapper = ft.Container(
            content=mobile_shell,
            alignment=ft.Alignment(0, 0),
            expand=True
        )
        page.add(wrapper)
        page.update()

    # --- ૧. LOGIN & REGISTER SCREEN ---
    def show_auth():
        global generated_otp
        page.scroll = None

        mobile_in = ft.TextField(label="૧૦ અંકનો મોબાઈલ નંબર", prefix_icon="phone", dense=True, max_length=10)
        pass_in = ft.TextField(label="પાસવર્ડ (૬ થી ૮ અક્ષર)", password=True, can_reveal_password=True, prefix_icon="lock", dense=True, max_length=8)
        repass_in = ft.TextField(label="ફરી પાસવર્ડ લખો (Re-Password)", password=True, can_reveal_password=True, prefix_icon="lock", dense=True, max_length=8)
        otp_in = ft.TextField(label="૬ અંકનો OTP દાખલ કરો", prefix_icon="security", dense=True, max_length=6)

        is_register_mode = False
        otp_sent = False

        resend_btn = ft.TextButton("🔄 Resend OTP", visible=False)
        timer_text = ft.Text("", size=11, color="grey", visible=False)
        mode_text = ft.Text("નવું એકાઉન્ટ બનાવવા અહીં ક્લિક કરો (Register)", color="cyan", size=12)

        def trigger_otp_send():
            global generated_otp
            generated_otp = str(random.randint(100000, 999999))
            otp_in.value = generated_otp

            dlg_otp = ft.AlertDialog(
                title=ft.Text("તમારો રજિસ્ટ્રેશન OTP", size=16, color="lightblue"),
                content=ft.Column([
                    ft.Text(f"{generated_otp}", size=30, weight=ft.FontWeight.BOLD, color="green"),
                    ft.Text("આ OTP નીચે આપોઆપ આવી ગયો છે.", size=11, color="grey")
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                actions=[ft.TextButton("ઓકે (OK)", on_click=lambda e: close_dialog(dlg_otp))],
                open=True
            )
            page.overlay.append(dlg_otp)
            page.update()

        def close_dialog(d):
            d.open = False
            page.update()

        def start_resend_timer():
            resend_btn.disabled = True
            timer_text.visible = True
            page.update()

            def countdown():
                for i in range(30, 0, -1):
                    timer_text.value = f"ફરી મોકલવા: {i}s"
                    page.update()
                    time.sleep(1)
                resend_btn.disabled = False
                timer_text.value = ""
                page.update()

            threading.Thread(target=countdown, daemon=True).start()

        def on_resend_click(e):
            trigger_otp_send()
            show_snack("નવો OTP આવી ગયો છે!", "cyan")
            start_resend_timer()

        resend_btn.on_click = on_resend_click

        def switch_mode(e):
            nonlocal is_register_mode, otp_sent
            is_register_mode = not is_register_mode
            otp_sent = False
            repass_in.visible = is_register_mode
            otp_in.visible = False
            resend_btn.visible = False
            timer_text.visible = False
            submit_btn.content.value = "Send OTP & Register" if is_register_mode else "Login"
            mode_text.value = "પહેલેથી ખાતું છે? લૉગિન કરો" if is_register_mode else "નવું એકાઉન્ટ બનાવવા અહીં ક્લિક કરો (Register)"
            page.update()

        repass_in.visible = False
        otp_in.visible = False

        def auth_action(e):
            global current_user, user_atms, generated_otp, selected_atm
            nonlocal otp_sent

            mob = mobile_in.value.strip()
            p = pass_in.value.strip()
            rep = repass_in.value.strip()

            if not mob or len(mob) != 10 or not mob.isdigit():
                show_snack("સાચો ૧૦ અંકનો મોબાઈલ નંબર નાખો!", "red")
                return

            if len(p) < 6 or len(p) > 8:
                show_snack("પાસવર્ડ ૬ થી ૮ અક્ષરનો જ રાખો!", "orange")
                return

            if is_register_mode:
                if p != rep:
                    show_snack("Password અને Re-Password બંને એકસરખા હોવા જોઈએ!", "red")
                    return

                userData = fb_get(f"users/{mob}")

                if not otp_sent:
                    if userData:
                        show_snack("આ નંબર પહેલેથી રજીસ્ટર થયેલો છે! લૉગિન કરો.", "orange")
                        return

                    otp_sent = True
                    otp_in.visible = True
                    resend_btn.visible = True
                    submit_btn.content.value = "Verify OTP & Complete"
                    trigger_otp_send()
                    start_resend_timer()
                    page.update()
                    return
                else:
                    user_entered_otp = otp_in.value.strip()
                    if user_entered_otp != generated_otp:
                        show_snack("ખોટો OTP! સાચો OTP દાખલ કરો.", "red")
                        return

                    fb_put(f"users/{mob}", {"password": p, "atms": {}})
                    current_user = mob
                    user_atms = {}
                    selected_atm = None
                    show_snack("રજિસ્ટ્રેશન સફળ થઈ ગયું છે!", "green")
                    show_main_panel()
            else:
                userData = fb_get(f"users/{mob}")
                if not userData or userData.get("password") != p:
                    show_snack("ખોટો મોબાઈલ નંબર અથવા પાસવર્ડ!", "red")
                else:
                    current_user = mob
                    user_atms = userData.get("atms", {})
                    if user_atms:
                        selected_atm = list(user_atms.keys())[0]
                    else:
                        selected_atm = None
                    show_main_panel()

        submit_btn = ft.Container(
            content=ft.Text("Login", weight=ft.FontWeight.BOLD, color="white"),
            bgcolor="blue",
            padding=10,
            border_radius=8,
            alignment=ft.Alignment(0, 0),
            on_click=auth_action
        )

        auth_layout = ft.Column(
            [
                ft.Image(
                    src="https://images.unsplash.com/photo-1548839140-29a749e1bc4e?w=400&q=80",
                    width=120,
                    height=85,
                    fit="cover",
                    border_radius=12
                ),
                ft.Text("Zevia PureX", size=22, weight=ft.FontWeight.BOLD, color="lightblue"),
                ft.Text("Smart Water ATM Enterprise", size=11, color="grey"),
                ft.Container(height=4),
                mobile_in,
                pass_in,
                repass_in,
                otp_in,
                ft.Row([resend_btn, timer_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=4),
                submit_btn,
                ft.TextButton(content=mode_text, on_click=switch_mode)
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
            scroll=ft.ScrollMode.ADAPTIVE
        )

        render_screen(auth_layout)

    # --- ૨. મેઈન પેનલ (બધા ફીચર્સ સામે જ દેખાશે) ---
    def show_main_panel():
        global selected_atm, user_atms, current_session_id

        # નવો સેશન શરુ કરીએ છીએ જેથી જૂના બેકગ્રાઉન્ડ થ્રેડ બંધ થઇ જાય
        current_session_id = int(time.time() * 1000)
        session_id = current_session_id

        is_connected = bool(selected_atm and selected_atm in user_atms)

        status_data = fb_get(f"atms/{selected_atm}/status") if is_connected else {}
        settings_data = fb_get(f"atms/{selected_atm}/settings") if is_connected else {}

        status_data = status_data or {}
        settings_data = settings_data or {}

        is_online = status_data.get("online", False) if is_connected else False
        rssi = status_data.get("wifi_rssi", -100) if is_connected else -65
        norm_level = status_data.get("normal_tank_level", 0.0) if is_connected else 85.0
        ice_level = status_data.get("ice_tank_level", 0.0) if is_connected else 60.0
        net_usage = status_data.get("data_usage_mb", 0.0) if is_connected else 1.25

        def add_atm_dialog(e):
            aid_in = ft.TextField(label="ATM ID (દા.ત. ATM_01)", dense=True)
            aname_in = ft.TextField(label="મશીન નામ (દા.ત. મુખ્ય બજાર)", dense=True)
            apass_in = ft.TextField(label="ATM Master Pass", password=True, dense=True)

            def save_atm(ev):
                global user_atms, selected_atm
                aid = aid_in.value.strip().upper()
                aname = aname_in.value.strip()
                apass = apass_in.value.strip()

                if not aid or not apass:
                    show_snack("ID અને પાસવર્ડ જરૂરી છે!", "red")
                    return

                atm_cloud = fb_get(f"atms/{aid}")
                if not atm_cloud:
                    show_snack(f"મશીન '{aid}' ઓનલાઇન નથી! નવો કોડ અપલોડ કરી ઓન કરો.", "red")
                    return

                cloud_settings = atm_cloud.get("settings", {})
                correct_pass = str(cloud_settings.get("master_pass", "258258"))

                if apass != correct_pass:
                    show_snack("ખોટો ATM પાસવર્ડ! કનેક્શન નકારાયું.", "red")
                    return

                fb_put(f"users/{current_user}/atms/{aid}", {"name": aname or aid, "password": apass})
                user_atms[aid] = {"name": aname or aid, "password": apass}
                selected_atm = aid
                dlg.open = False
                show_snack(f"{aid} સફળતાપૂર્વક કનેક્ટ થઈ ગયું!", "green")
                show_main_panel()

            btn_save = ft.TextButton("જોડો (Connect)", on_click=save_atm)
            dlg = ft.AlertDialog(
                title=ft.Text("નવું ATM કનેક્ટ કરો", size=15),
                content=ft.Column([aid_in, aname_in, apass_in], tight=True, spacing=8),
                actions=[btn_save],
                open=True,
            )
            page.overlay.append(dlg)
            page.update()

        def switch_atm_dialog(e):
            if not user_atms:
                add_atm_dialog(e)
                return

            atm_options = []
            for aid, ainfo in user_atms.items():
                def make_sel(target_aid):
                    def do_sel(ev):
                        global selected_atm
                        selected_atm = target_aid
                        dlg_sw.open = False
                        show_main_panel()
                    return do_sel

                is_current = (aid == selected_atm)
                atm_options.append(
                    ft.ListTile(
                        leading=ft.Icon("check_circle" if is_current else "local_drink", color="green" if is_current else "blue"),
                        title=ft.Text(ainfo.get("name", aid), weight=ft.FontWeight.BOLD, size=13, color="green" if is_current else None),
                        subtitle=ft.Text(f"ID: {aid}"),
                        on_click=make_sel(aid)
                    )
                )

            dlg_sw = ft.AlertDialog(
                title=ft.Text("ATM પસંદ કરો", size=15),
                content=ft.Column(atm_options, tight=True, spacing=4),
                actions=[
                    ft.TextButton("➕ નવું ATM જોડો", on_click=lambda ev: [setattr(dlg_sw, 'open', False), page.update(), add_atm_dialog(ev)])
                ],
                open=True
            )
            page.overlay.append(dlg_sw)
            page.update()

        # --- TAB 1: CONTROL UI VARIABLES (For Auto-Refresh) ---
        amount_in = ft.TextField(label="રકમ (Rs.)", value="10", keyboard_type=ft.KeyboardType.NUMBER, dense=True, disabled=not is_connected)
        wtype_drop = ft.Dropdown(
            label="પાણીનો પ્રકાર",
            value="1",
            dense=True,
            disabled=not is_connected,
            options=[
                ft.dropdown.Option("1", "Normal Water"),
                ft.dropdown.Option("2", "Ice Water"),
            ],
        )

        lbl_status_val = ft.Text("ONLINE" if is_online else ("DISABLED" if not is_connected else "OFFLINE"), color="green" if is_online else "orange", weight=ft.FontWeight.BOLD, size=12)
        lbl_wifi_net = ft.Text(f"Wi-Fi: {rssi} dBm | Net વપરાશ: {net_usage:.2f} MB", size=11, color="grey" if not is_connected else "white")
        pb_wifi = ft.ProgressBar(value=(rssi + 100) / 70 if rssi != -100 else 0, color="blue" if is_connected else "grey")

        lbl_norm_tank = ft.Text(f"Normal Tank: {norm_level}%", size=11, color="grey" if not is_connected else "white")
        pb_norm_tank = ft.ProgressBar(value=norm_level / 100, color="cyan" if is_connected else "grey")
        
        lbl_ice_tank = ft.Text(f"Ice Tank: {ice_level}%", size=11, color="grey" if not is_connected else "white")
        pb_ice_tank = ft.ProgressBar(value=ice_level / 100, color="blue" if is_connected else "grey")

        upi_list_view = ft.Column(spacing=4)
        lbl_today_upi_total = ft.Text("Today: Rs. 0.0", weight=ft.FontWeight.BOLD, size=12, color="green" if is_connected else "grey")

        # UPI ડેટા લાઈવ સ્ક્રીન પર લાવવા માટેનું ફંક્શન
        def render_upi_items(upi_dict=None):
            upi_list_view.controls.clear()
            if not is_connected:
                return

            if not upi_dict:
                # જો ફાયરબેઝમાં ડેટા ન હોય તો ડેમો ડેટા બતાવો
                lbl_today_upi_total.value = "Today: Rs. 350.0"
                for i in range(3):
                    upi_list_view.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(f"Rs. {10 + i*10}.0 (UPI)", weight=ft.FontWeight.BOLD, color="green", size=12),
                                    ft.Text(f"ID: pay_Live{random.randint(1000,9999)}..", size=10, color="grey")
                                ], spacing=1),
                                ft.Text(f"Today 10:{45 - (i*12)} AM", size=10, color="lightblue")
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=5,
                            bgcolor="#1A1E24",
                            border_radius=5
                        )
                    )
                return

            # અસલ (Live) ડેટા ફાયરબેઝમાંથી આવ્યો હોય તો 
            items = list(upi_dict.values())
            items.reverse() # સૌથી નવું પેમેન્ટ સૌથી ઉપર દેખાશે
            today_total = sum(float(x.get("amount", 0)) for x in items)
            lbl_today_upi_total.value = f"Today: Rs. {today_total}"

            for idx, txn in enumerate(items):
                if idx >= 3: break # માત્ર છેલ્લા ૩ જ બતાવશે
                amt = float(txn.get("amount", 0))
                upi_list_view.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"Rs. {amt} (UPI)", weight=ft.FontWeight.BOLD, color="green", size=12),
                                ft.Text(f"ID: {txn.get('id', 'pay_xxx')[:12]}..", size=10, color="grey")
                            ], spacing=1),
                            ft.Text(f"{txn.get('time', 'Live')}", size=10, color="lightblue")
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=5,
                        bgcolor="#1A1E24",
                        border_radius=5
                    )
                )

        # શરૂઆતમાં એકવાર UPI ડેટા લાવી દઈએ
        render_upi_items(fb_get(f"atms/{selected_atm}/upi_transactions") if is_connected else None)

        # --- 5 SECOND AUTO-REFRESH BACKGROUND WORKER ---
        def auto_refresh_worker(sid):
            while current_session_id == sid:
                time.sleep(5) # દર ૫ સેકન્ડે ચેક કરશે
                if current_session_id != sid: break
                if not is_connected: continue

                try:
                    new_status = fb_get(f"atms/{selected_atm}/status") or {}
                    _is_on = new_status.get("online", False)
                    _rssi = new_status.get("wifi_rssi", -100)
                    _nl = new_status.get("normal_tank_level", 0.0)
                    _il = new_status.get("ice_tank_level", 0.0)
                    _net = new_status.get("data_usage_mb", 0.0)

                    # UI કંટ્રોલ્સના વેલ્યુ જાતે જ અપડેટ કરી દેશે
                    lbl_status_val.value = "ONLINE" if _is_on else "OFFLINE"
                    lbl_status_val.color = "green" if _is_on else "orange"
                    lbl_wifi_net.value = f"Wi-Fi: {_rssi} dBm | Net વપરાશ: {_net:.2f} MB"
                    pb_wifi.value = (_rssi + 100) / 70 if _rssi != -100 else 0

                    lbl_norm_tank.value = f"Normal Tank: {_nl}%"
                    pb_norm_tank.value = _nl / 100
                    lbl_ice_tank.value = f"Ice Tank: {_il}%"
                    pb_ice_tank.value = _il / 100

                    # નવું UPI ટ્રાન્ઝેક્શન ચેક કરો
                    new_upi = fb_get(f"atms/{selected_atm}/upi_transactions")
                    if new_upi:
                        render_upi_items(new_upi)

                    page.update()
                except Exception:
                    break

        if is_connected:
            threading.Thread(target=auto_refresh_worker, args=(session_id,), daemon=True).start()

        def trigger_dispense(e):
            if not is_connected:
                show_snack("મશીન કનેક્ટ થયેલ નથી! પાણી કાઢી શકાશે નહીં.", "orange")
                return
            amt = float(amount_in.value or 0.0)
            wtype = int(wtype_drop.value)
            if amt <= 0:
                show_snack("માન્ય રકમ દાખલ કરો", "red")
                return
            cmd = {
                "cmd": "DISPENSE",
                "type": wtype,
                "amount": amt,
                "timestamp": int(time.time()),
            }
            fb_put(f"atms/{selected_atm}/app_command", cmd)
            show_snack(f"Rs. {amt} નું પાણી શરૂ કરવાનો કમાન્ડ મોકલાયો!")

        btn_disp = ft.Container(
            content=ft.Text("OK - પાણી શરૂ કરો" if is_connected else "🔒 લૉક છે (Add ATM First)", color="white", weight=ft.FontWeight.BOLD, size=12),
            bgcolor="green" if is_connected else "#2A303A",
            padding=10,
            border_radius=8,
            alignment=ft.Alignment(0, 0),
            on_click=trigger_dispense
        )

        def show_upi_history(e):
            if not is_connected:
                show_snack("પહેલા ATM કનેક્ટ કરો", "orange")
                return
                
            day_wise_list = ft.ListView(expand=True, spacing=5, padding=5)
            for i in range(1, 31):
                date_str = (datetime.now() - timedelta(days=i)).strftime("%d %b %Y")
                day_wise_list.controls.append(
                    ft.Row([ft.Text(f"{date_str}", size=12), ft.Text(f"Rs. {random.randint(100, 500)}.0", size=12, weight=ft.FontWeight.BOLD, color="green")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )

            month_wise_list = ft.ListView(expand=True, spacing=5, padding=5)
            for i in range(1, 7):
                month_str = (datetime.now() - timedelta(days=i*30)).strftime("%b %Y")
                month_wise_list.controls.append(
                    ft.Row([ft.Text(f"{month_str}", size=12), ft.Text(f"Rs. {random.randint(3000, 15000)}.0", size=12, weight=ft.FontWeight.BOLD, color="green")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )

            history_tabs = ft.Tabs(
                selected_index=0,
                animation_duration=300,
                tabs=[
                    ft.Tab(
                        text="1 મહિનો (Day)",
                        content=ft.Container(content=day_wise_list, padding=10)
                    ),
                    ft.Tab(
                        text="6 મહિના (Month)",
                        content=ft.Container(content=month_wise_list, padding=10)
                    ),
                ],
                expand=True,
            )

            dlg_history = ft.AlertDialog(
                title=ft.Text("UPI ટ્રાન્ઝેક્શન હિસ્ટ્રી", size=15, weight=ft.FontWeight.BOLD, color="lightblue"),
                content=ft.Container(width=300, height=400, content=history_tabs),
                actions=[ft.TextButton("બંધ કરો (Close)", on_click=lambda ev: close_dlg(dlg_history))],
                open=True
            )
            
            def close_dlg(d):
                d.open = False
                page.update()

            page.overlay.append(dlg_history)
            page.update()

        tab1 = ft.Column([
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text("મશીન સ્ટેટસ:", size=12),
                            lbl_status_val,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        lbl_wifi_net,
                        pb_wifi,
                    ]),
                    padding=10
                )
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("વોટર ટેન્ક લેવલ (Tank Levels)", weight=ft.FontWeight.BOLD, size=12),
                        lbl_norm_tank,
                        pb_norm_tank,
                        lbl_ice_tank,
                        pb_ice_tank,
                    ]),
                    padding=10
                )
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("મોબાઇલમાંથી પાણી કાઢો", weight=ft.FontWeight.BOLD, size=12),
                        amount_in,
                        wtype_drop,
                        btn_disp
                    ]),
                    padding=10
                )
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text("લાઈવ UPI ટ્રાન્ઝેક્શન્સ", weight=ft.FontWeight.BOLD, size=12),
                            lbl_today_upi_total
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=2),
                        upi_list_view,
                        ft.Container(
                            content=ft.Text("વધુ જુઓ (View History)", size=11, color="cyan" if is_connected else "grey", text_align=ft.TextAlign.CENTER),
                            alignment=ft.Alignment(0, 0),
                            on_click=show_upi_history if is_connected else None,
                            padding=5
                        )
                    ]),
                    padding=10
                )
            )
        ], spacing=5, scroll=ft.ScrollMode.ADAPTIVE, expand=True)

        # --- TAB 2: SETTINGS ---
        np_in = ft.TextField(label="Normal Price", value=str(settings_data.get("n_price", 0.5)), disabled=not is_connected, dense=True)
        ip_in = ft.TextField(label="Ice Price", value=str(settings_data.get("i_price", 1.0)), disabled=not is_connected, dense=True)
        nc_in = ft.TextField(label="Normal Cali", value=str(settings_data.get("n_cal", 450.0)), disabled=not is_connected, dense=True)
        ic_in = ft.TextField(label="Ice Cali", value=str(settings_data.get("i_cal", 450.0)), disabled=not is_connected, dense=True)
        nt_in = ft.TextField(label="Normal Target (L)", value=str(settings_data.get("n_target", 20.0)), disabled=not is_connected, dense=True)
        it_in = ft.TextField(label="Ice Target (L)", value=str(settings_data.get("i_target", 20.0)), disabled=not is_connected, dense=True)

        atm_master_pass_in = ft.TextField(label="ATM Master Pass (૬-૮ અક્ષર)", value=str(settings_data.get("master_pass", "258258")), disabled=not is_connected, dense=True, max_length=8)
        app_sec_pass_in = ft.TextField(label="Settings PIN (૬-૮ અક્ષર)", value=str(settings_data.get("sec_pin", "25802580")), disabled=not is_connected, dense=True, max_length=8)

        def save_settings(e):
            if not is_connected:
                show_snack("મશીન કનેક્ટ થયેલ નથી!", "orange")
                return
            new_set = {
                "n_price": float(np_in.value),
                "i_price": float(ip_in.value),
                "n_cal": float(nc_in.value),
                "i_cal": float(ic_in.value),
                "n_target": float(nt_in.value),
                "i_target": float(it_in.value),
                "auto_fill": settings_data.get("auto_fill", 1),
                "master_pass": atm_master_pass_in.value.strip(),
                "sec_pin": app_sec_pass_in.value.strip()
            }
            fb_put(f"atms/{selected_atm}/settings", new_set)
            show_snack("સેટિંગ્સ સેવ થઈ ગયા!")

        save_btn = ft.Container(
            content=ft.Text("Update Settings", color="white", weight=ft.FontWeight.BOLD),
            bgcolor="blue" if is_connected else "#2A303A",
            padding=10,
            border_radius=8,
            alignment=ft.Alignment(0, 0),
            on_click=save_settings
        )

        tab2 = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Calibration & Rates (સેટિંગ્સ)", weight=ft.FontWeight.BOLD, size=13),
                    np_in, ip_in, nc_in, ic_in, nt_in, it_in,
                    ft.Divider(height=5),
                    ft.Text("સિક્યોરિટી અને પાસવર્ડ ચેન્જ", weight=ft.FontWeight.BOLD, size=13, color="orange"),
                    atm_master_pass_in,
                    app_sec_pass_in,
                    save_btn
                ], spacing=6, scroll=ft.ScrollMode.ADAPTIVE),
                padding=10
            )
        )

        # --- TAB 3: CARDS ---
        demo_cards = [
            ft.Card(
                content=ft.Container(
                    content=ft.Row([
                        ft.Row([
                            ft.Icon("credit_card", color="green" if is_connected else "grey", size=22),
                            ft.Column([
                                ft.Text("Card No: 1", weight=ft.FontWeight.BOLD, size=12),
                                ft.Text("Bal: Rs.150.0 | 45.2L", size=10, color="grey")
                            ], spacing=1)
                        ]),
                        ft.Container(
                            content=ft.Text("Recharge" if is_connected else "Locked", color="cyan" if is_connected else "grey", size=11),
                            padding=5
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=8
                )
            )
        ]

        tab3 = ft.Container(
            content=ft.Column([
                ft.Text("કસ્ટમર કાર્ડ લિસ્ટ", weight=ft.FontWeight.BOLD, size=13),
                ft.Column(demo_cards, spacing=5),
                ft.Text("મશીન કનેક્ટ થયા પછી કાર્ડ લાઈવ દેખાશે અને રિચાર્જ થશે.", color="grey", size=11)
            ], spacing=6),
            padding=5
        )

        # --- TAB 4: HISAB ---
        tab4 = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("આજનો હિસાબ (Daily Hisab)", weight=ft.FontWeight.BOLD, size=14, color="lightblue"),
                    ft.Divider(height=5),
                    ft.Row([ft.Text("Coin:"), ft.Text("Rs. 250.0" if is_connected else "Rs. 0.0", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("UPI:"), ft.Text("Rs. 180.0" if is_connected else "Rs. 0.0", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Card:"), ft.Text("Rs. 400.0" if is_connected else "Rs. 0.0", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("App Dispense:"), ft.Text("Rs. 50.0" if is_connected else "Rs. 0.0", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=5),
                    ft.Row([ft.Text("કુલ આવક:", size=13), ft.Text("Rs. 880.0" if is_connected else "Rs. 0.0", size=13, weight=ft.FontWeight.BOLD, color="green")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=4),
                padding=10
            )
        )

        content_holder = ft.Container(content=tab1, padding=2, expand=True)

        def verify_settings_pass():
            saved_pin = str(settings_data.get("sec_pin", "25802580")) if is_connected else "25802580"
            pin_in = ft.TextField(label="ગુપ્ત PIN દાખલ કરો", password=True, dense=True)

            def check_pin(e):
                if pin_in.value.strip() == saved_pin:
                    dlg_pin.open = False
                    content_holder.content = tab2
                    page.update()
                else:
                    show_snack("ખોટો સિક્યોરિટી પિન!", "red")

            chk_btn = ft.TextButton("Unlock", on_click=check_pin)
            dlg_pin = ft.AlertDialog(
                title=ft.Text("સેટિંગ્સ લોક છે", size=14),
                content=pin_in,
                actions=[chk_btn],
                open=True
            )
            page.overlay.append(dlg_pin)
            page.update()

        def switch_tab(tab_name):
            if tab_name == "tab1":
                content_holder.content = tab1
            elif tab_name == "tab2":
                verify_settings_pass()
                return
            elif tab_name == "tab3":
                content_holder.content = tab3
            elif tab_name == "tab4":
                content_holder.content = tab4
            page.update()

        tab_nav_bar = ft.Container(
            content=ft.Row(
                [
                    ft.TextButton("કંટ્રોલ", on_click=lambda e: switch_tab("tab1")),
                    ft.TextButton("સેટિંગ્સ", on_click=lambda e: switch_tab("tab2")),
                    ft.TextButton("કાર્ડ્સ", on_click=lambda e: switch_tab("tab3")),
                    ft.TextButton("હિસાબ", on_click=lambda e: switch_tab("tab4")),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
            bgcolor="#1A1E24",
            padding=2,
            border_radius=6,
        )

        atm_display_name = user_atms.get(selected_atm, {}).get("name", selected_atm) if is_connected else "નવું ATM જોડો"
        atm_btn_text = f"🏧 {atm_display_name}" if is_connected else "➕ Add ATM"
        atm_btn_color = "blue" if is_connected else "orange"

        header = ft.Row(
            [
                ft.Container(
                    content=ft.Text(atm_btn_text, size=12, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor=atm_btn_color,
                    padding=6,
                    border_radius=6,
                    on_click=switch_atm_dialog
                ),
                ft.Row([
                    ft.Container(
                        content=ft.Text("રીફ્રેશ", size=12, color="cyan"),
                        padding=4,
                        on_click=lambda e: show_main_panel()
                    ),
                    ft.Container(
                        content=ft.Text("લૉગઆઉટ", size=12, color="red"),
                        padding=4,
                        on_click=lambda e: show_auth()
                    )
                ], spacing=10)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        panel_layout = ft.Column([header, tab_nav_bar, ft.Divider(height=5), content_holder], expand=True)
        render_screen(panel_layout)

    show_auth()

if __name__ == "__main__":
    if hasattr(ft, "run_app"):
        ft.run_app(main)
    elif hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
