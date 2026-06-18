import os
import sys
import json
import hashlib
import hmac
import secrets
import time
import psutil
import requests
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Response, stream_with_context, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ADMIN_IDS, USER_PROXIES_FILE, VPN_DIR, BACKUP_DIR, ALLOWED_CHAT_ID, BOT_TOKEN
from database.storage import load_json, save_json
from utils.logger import standard_logger, audit_logger
from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry, get_vpn_config_age, get_proxy_age
from web.amnezia_config import AMNEZIA_LINKS, VERSION_CONFLICT_WARNING, UNIVERSAL_TEMPLATE

# ==========================================
# ЧТЕНИЕ .env
# ==========================================

def load_env():
    """Загружает переменные из .env файла"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

ENV_VARS = load_env()

# ==========================================
# FLASK ПРИЛОЖЕНИЕ
# ==========================================

app = Flask(__name__)
_secret_seed = ENV_VARS.get('WEB_PASSWORD', 'default_secret')
app.secret_key = hashlib.sha256(_secret_seed.encode()).hexdigest()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==========================================
# ХРАНИЛИЩА В ПАМЯТИ
# ==========================================

two_factor_codes = {}
login_history_file = 'bot_data/web_logins.json'

def check_telegram_auth(data: dict) -> bool:
    """Проверяет подпись Telegram Login Widget"""
    if not BOT_TOKEN:
        return False
    
    check_hash = data.pop('hash', '')
    data_check_arr = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(data_check_arr)
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if hash_value != check_hash:
        return False
    
    auth_date = int(data.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        return False
    
    return True

# ==========================================
# АУТЕНТИФИКАЦИЯ
# ==========================================

def get_web_password():
    return ENV_VARS.get('WEB_PASSWORD', 'default_password')

class User(UserMixin):
    def __init__(self, id, username=None, is_telegram=False):
        self.id = id
        self.username = username or str(id)
        self.is_telegram = is_telegram

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('tg_'):
        tg_id = user_id[3:]
        return User(tg_id, username=f"TG:{tg_id}", is_telegram=True)
    return User(user_id)

def check_auth(password):
    return password == get_web_password()

def record_login(user_id, method, ip, success=True):
    """Записывает вход в журнал"""
    logins = load_json(login_history_file, [])
    logins.append({
        'user_id': str(user_id),
        'method': method,
        'ip': ip,
        'time': datetime.now().isoformat(),
        'success': success
    })
    logins = logins[-500:]
    save_json(login_history_file, logins)

# ==========================================
# МАРШРУТЫ АУТЕНТИФИКАЦИИ
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if check_auth(password):
            user = User('admin')
            login_user(user)
            record_login('admin', 'password', request.remote_addr, True)
            audit_logger.info(f"ACTION:WEB_LOGIN | USER:admin | IP:{request.remote_addr} | METHOD:PASSWORD")
            
            if ENV_VARS.get('WEB_2FA_ENABLED', 'false').lower() == 'true':
                code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
                two_factor_codes['admin'] = {
                    'code': code,
                    'expires': time.time() + 300
                }
                session['pending_2fa'] = 'admin'
                
                try:
                    admin_id = ADMIN_IDS[0] if ADMIN_IDS else None
                    if admin_id:
                        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                        requests.post(url, json={
                            'chat_id': admin_id,
                            'text': f"🔐 <b>Код подтверждения для входа в веб-панель</b>\n\n"
                                    f"<code>{code}</code>\n\n"
                                    f"⏰ Действителен 5 минут\n"
                                    f"🌐 IP: {request.remote_addr}",
                            'parse_mode': 'HTML'
                        })
                except Exception as e:
                    audit_logger.error(f"ACTION:WEB_2FA_SEND_FAILED | ERROR:{e}")
                
                flash('Код подтверждения отправлен в Telegram', 'info')
                return redirect(url_for('verify_2fa'))
            
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('dashboard'))
        else:
            record_login('unknown', 'password', request.remote_addr, False)
            audit_logger.warning(f"ACTION:WEB_LOGIN_FAILED | IP:{request.remote_addr}")
            flash('Неверный пароль', 'danger')
    
    return render_template('login.html', bot_username=ENV_VARS.get('TELEGRAM_BOT_USERNAME', ''))

@app.route('/login/telegram', methods=['POST'])
def login_telegram():
    """Вход через Telegram Login Widget"""
    data = request.get_json()
    
    if not check_telegram_auth(data):
        audit_logger.warning(f"ACTION:WEB_TELEGRAM_LOGIN_FAILED | IP:{request.remote_addr}")
        return jsonify({'success': False, 'error': 'Неверная подпись Telegram'}), 403
    
    user_id = data.get('id')
    username = data.get('username') or f"TG:{user_id}"
    
    if int(user_id) not in ADMIN_IDS:
        audit_logger.warning(f"ACTION:WEB_TELEGRAM_LOGIN_UNAUTHORIZED | USER:{user_id} | IP:{request.remote_addr}")
        return jsonify({'success': False, 'error': 'Доступ запрещён'}), 403
    
    user = User(str(user_id), username=username, is_telegram=True)
    login_user(user)
    record_login(user_id, 'telegram', request.remote_addr, True)
    audit_logger.info(f"ACTION:WEB_LOGIN | USER:{user_id} | IP:{request.remote_addr} | METHOD:TELEGRAM")
    
    flash(f'Добро пожаловать, @{username}!', 'success')
    return jsonify({'success': True, 'redirect': url_for('dashboard')})

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    """Подтверждение 2FA кода"""
    pending = session.get('pending_2fa')
    if not pending:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        stored = two_factor_codes.get(pending)
        
        if stored and stored['code'] == code and time.time() < stored['expires']:
            user = User(pending)
            login_user(user)
            session['2fa_passed'] = True
            del two_factor_codes[pending]
            del session['pending_2fa']
            record_login(pending, '2fa', request.remote_addr, True)
            audit_logger.info(f"ACTION:WEB_2FA_SUCCESS | USER:{pending} | IP:{request.remote_addr}")
            flash('Вход подтверждён!', 'success')
            return redirect(url_for('dashboard'))
        else:
            record_login(pending, '2fa', request.remote_addr, False)
            audit_logger.warning(f"ACTION:WEB_2FA_FAILED | USER:{pending} | IP:{request.remote_addr}")
            flash('Неверный или просроченный код', 'danger')
    
    return render_template('verify_2fa.html')

@app.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    session.clear()
    audit_logger.info(f"ACTION:WEB_LOGOUT | USER:{user_id}")
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

# ==========================================
# ДАШБОРД
# ==========================================

@app.route('/')
@login_required
def dashboard():
    """Главная страница со статистикой"""
    vpn_expired, vpn_expiring = check_all_vpn_expiry()
    proxy_expired, proxy_expiring = check_all_proxy_expiry()
    
    stats = load_json('bot_data/stats.json', {})
    total_users = len(stats)
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    total_proxies = sum(len(data.get('proxies', [])) for data in user_proxies.values())
    
    total_vpn = 0
    if os.path.exists(VPN_DIR):
        for user_dir in os.listdir(VPN_DIR):
            user_path = os.path.join(VPN_DIR, user_dir)
            if os.path.isdir(user_path):
                total_vpn += len([f for f in os.listdir(user_path) if f.endswith('.vpn')])
    
    chart_data = {
        'users': [data.get('username', f"ID:{uid}")[:10] for uid, data in list(stats.items())[:7]],
        'actions': [sum(data.get('actions', {}).values()) for uid, data in list(stats.items())[:7]]
    }
    
    bot_logs = []
    audit_logs = []
    
    bot_log_path = 'bot_data/logs/bot.log'
    audit_log_path = 'bot_data/logs/audit.log'
    
    if os.path.exists(bot_log_path):
        with open(bot_log_path, 'r', encoding='utf-8') as f:
            bot_logs = f.readlines()[-20:]
    
    if os.path.exists(audit_log_path):
        with open(audit_log_path, 'r', encoding='utf-8') as f:
            audit_logs = f.readlines()[-20:]
    
    return render_template('dashboard.html',
                          vpn_expired=len(vpn_expired),
                          vpn_expiring=len(vpn_expiring),
                          proxy_expired=len(proxy_expired),
                          proxy_expiring=len(proxy_expiring),
                          total_users=total_users,
                          total_proxies=total_proxies,
                          total_vpn=total_vpn,
                          bot_logs=bot_logs,
                          audit_logs=audit_logs,
                          chart_data=json.dumps(chart_data))

# ==========================================
# УПРАВЛЕНИЕ VPN
# ==========================================

@app.route('/vpn')
@login_required
def vpn_management():
    users_vpn = {}
    
    if os.path.exists(VPN_DIR):
        for username in os.listdir(VPN_DIR):
            user_dir = os.path.join(VPN_DIR, username)
            if os.path.isdir(user_dir):
                configs = []
                for conf in os.listdir(user_dir):
                    if conf.endswith('.vpn'):
                        conf_path = os.path.join(user_dir, conf)
                        try:
                            age = get_vpn_config_age(username, conf)
                        except Exception:
                            age = {'status': 'unknown', 'days_left': 0}
                        configs.append({
                            'name': conf,
                            'size': os.path.getsize(conf_path),
                            'created': datetime.fromtimestamp(os.path.getctime(conf_path)).strftime('%d.%m.%Y %H:%M'),
                            'status': age['status'],
                            'days_left': age.get('days_left', 0)
                        })
                if configs:
                    users_vpn[username] = configs
    
    return render_template('vpn.html', users_vpn=users_vpn)

@app.route('/vpn/delete/<username>/<filename>', methods=['POST'])
@login_required
def delete_vpn_config(username, filename):
    if '..' in filename or '/' in filename:
        flash('Недопустимое имя файла', 'danger')
        return redirect(url_for('vpn_management'))
    
    user_dir = os.path.join(VPN_DIR, username)
    file_path = os.path.join(user_dir, filename)
    
    if not os.path.abspath(file_path).startswith(os.path.abspath(VPN_DIR)):
        flash('Попытка выхода за пределы директории', 'danger')
        return redirect(url_for('vpn_management'))
    
    if os.path.exists(file_path):
        os.remove(file_path)
        audit_logger.info(f"ACTION:VPN_DELETE | ADMIN:WEB | USER:{username} | FILE:{filename}")
        flash(f'Конфиг {filename} удалён', 'success')
    else:
        flash('Файл не найден', 'danger')
    
    return redirect(url_for('vpn_management'))

# ==========================================
# УПРАВЛЕНИЕ ПРОКСИ
# ==========================================

@app.route('/proxy')
@login_required
def proxy_management():
    user_proxies = load_json(USER_PROXIES_FILE, {})
    stats = load_json('bot_data/stats.json', {})
    
    grouped_proxies = {}
    total_count = 0
    
    for user_id, data in user_proxies.items():
        user_proxy_list = []
        for proxy in data.get('proxies', []):
            try:
                age = get_proxy_age(int(user_id), proxy['name'])
            except Exception:
                age = {'status': 'unknown', 'days_left': 0}
            
            user_proxy_list.append({
                'name': proxy['name'],
                'server': proxy['server'],
                'port': proxy['port'],
                'secret': proxy['secret'],
                'issued_at': proxy.get('issued_at', 'Unknown'),
                'issued_by': proxy.get('issued_by', 'Unknown'),
                'status': age['status'],
                'days_left': age.get('days_left', 0)
            })
            total_count += 1
        
        if user_proxy_list:
            user_data = stats.get(str(user_id), {})
            username = user_data.get('username') or f"ID:{user_id}"
            
            grouped_proxies[user_id] = {
                'username': username,
                'proxies': user_proxy_list,
                'count': len(user_proxy_list)
            }
    
    return render_template('proxy.html', 
                          grouped_proxies=grouped_proxies,
                          total_count=total_count,
                          total_users=len(grouped_proxies))

@app.route('/proxy/delete/<user_id>/<path:proxy_name>', methods=['POST'])
@login_required
def delete_proxy(user_id, proxy_name):
    user_proxies = load_json(USER_PROXIES_FILE, {})
    
    if user_id in user_proxies:
        original_count = len(user_proxies[user_id]['proxies'])
        user_proxies[user_id]['proxies'] = [
            p for p in user_proxies[user_id]['proxies'] if p['name'] != proxy_name
        ]
        new_count = len(user_proxies[user_id]['proxies'])
        
        if new_count == original_count:
            flash(f'Прокси "{proxy_name}" не найден', 'warning')
        else:
            if new_count == 0:
                del user_proxies[user_id]
            
            save_json(USER_PROXIES_FILE, user_proxies)
            audit_logger.info(f"ACTION:PROXY_DELETE | ADMIN:WEB | USER:{user_id} | PROXY:{proxy_name}")
            flash(f'Прокси "{proxy_name}" удалён', 'success')
    else:
        flash('Пользователь не найден', 'danger')
    
    return redirect(url_for('proxy_management'))

# ==========================================
# ПРОСМОТР ПРОБЛЕМ
# ==========================================

@app.route('/problems')
@login_required
def problems():
    problems_list = load_json('bot_data/problems.json', [])
    return render_template('problems.html', problems=problems_list)

@app.route('/problems/clear', methods=['POST'])
@login_required
def clear_problems():
    save_json('bot_data/problems.json', [])
    audit_logger.info(f"ACTION:PROBLEMS_CLEAR | ADMIN:WEB")
    flash('Список проблем очищен', 'success')
    return redirect(url_for('problems'))

# ==========================================
# ПУБЛИКАЦИЯ НОВОСТЕЙ
# ==========================================

@app.route('/news', methods=['GET', 'POST'])
@login_required
def news():
    """Публикация новостей"""
    if request.method == 'POST':
        news_text = request.form.get('news_text', '').strip()
        
        if not news_text:
            flash('Текст новости пустой', 'danger')
            return redirect(url_for('news'))
        
        if not ALLOWED_CHAT_ID:
            flash('ALLOWED_CHAT_ID не настроен', 'danger')
            return redirect(url_for('news'))
        
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            response = requests.post(url, json={
                'chat_id': ALLOWED_CHAT_ID,
                'text': news_text,
                'parse_mode': 'HTML'
            })
            
            if response.json().get('ok'):
                msg_id = response.json()['result']['message_id']
                audit_logger.info(f"ACTION:NEWS_PUBLISH | ADMIN:WEB | CHAT:{ALLOWED_CHAT_ID} | MSG_ID:{msg_id}")
                flash('Новость опубликована!', 'success')
            else:
                error = response.json().get('description', 'Неизвестная ошибка')
                flash(f'Ошибка публикации: {error}', 'danger')
        except Exception as e:
            flash(f'Ошибка: {e}', 'danger')
        
        return redirect(url_for('news'))
    
    return render_template('news.html', chat_id=ALLOWED_CHAT_ID)

@app.route('/news/templates')
@login_required
def news_templates():
    """Возвращает шаблоны для публикации"""
    def build_text(template):
        links_text = template["links_section"].format(**AMNEZIA_LINKS)
        return (
            f"{template['title']}\n\n"
            f"{template['body']}\n\n"
            f"{links_text}\n\n"
            f"{VERSION_CONFLICT_WARNING}"
        )
    
    def build_buttons(template):
        buttons = []
        for row in template["buttons"]:
            btn_row = []
            for btn in row:
                btn_row.append({
                    "text": btn["text"],
                    "url": AMNEZIA_LINKS[btn["url"]]
                })
            buttons.append(btn_row)
        return buttons
    
    return jsonify({
        "universal": {
            "text": build_text(UNIVERSAL_TEMPLATE),
            "buttons": build_buttons(UNIVERSAL_TEMPLATE),
            "name": "🔄 Обновление Amnezia (все платформы)"
        }
    })

@app.route('/news/publish-with-buttons', methods=['POST'])
@login_required
def news_publish_with_buttons():
    """Публикация новости с inline-кнопками"""
    data = request.get_json()
    
    news_text = data.get('text', '').strip()
    buttons = data.get('buttons', [])
    
    if not news_text:
        return jsonify({'success': False, 'error': 'Текст новости пустой'}), 400
    
    if not ALLOWED_CHAT_ID or not BOT_TOKEN:
        return jsonify({'success': False, 'error': 'ALLOWED_CHAT_ID или BOT_TOKEN не настроены'}), 400
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        reply_markup = None
        if buttons:
            reply_markup = {"inline_keyboard": buttons}
        
        payload = {
            'chat_id': ALLOWED_CHAT_ID,
            'text': news_text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            msg_id = result['result']['message_id']
            buttons_count = sum(len(row) for row in buttons) if buttons else 0
            audit_logger.info(
                f"ACTION:NEWS_PUBLISH_WITH_BUTTONS | ADMIN:WEB | "
                f"CHAT:{ALLOWED_CHAT_ID} | MSG_ID:{msg_id} | BUTTONS:{buttons_count}"
            )
            return jsonify({
                'success': True, 
                'message': f'Новость опубликована с {buttons_count} кнопками!',
                'message_id': msg_id
            })
        else:
            error = result.get('description', 'Неизвестная ошибка')
            return jsonify({'success': False, 'error': f'Ошибка Telegram: {error}'}), 400
            
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Таймаут соединения с Telegram'}), 504
    except Exception as e:
        audit_logger.error(f"ACTION:NEWS_PUBLISH_ERROR | ERROR:{e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# СИСТЕМНЫЙ МОНИТОРИНГ
# ==========================================

@app.route('/system')
@login_required
def system():
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    
    process_info = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            if 'python' in proc.info['name'].lower() or 'durdom' in proc.info['name'].lower():
                process_info.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    bot_running = False
    web_running = True
    try:
        import subprocess
        result = subprocess.run(['systemctl', 'is-active', 'durdom-bot'], 
                              capture_output=True, text=True)
        bot_running = result.stdout.strip() == 'active'
    except Exception:
        pass
    
    return render_template('system.html',
                          cpu_percent=cpu_percent,
                          cpu_count=cpu_count,
                          memory=memory,
                          disk=disk,
                          uptime=str(uptime).split('.')[0],
                          boot_time=boot_time.strftime('%d.%m.%Y %H:%M:%S'),
                          process_info=process_info,
                          bot_running=bot_running,
                          web_running=web_running)

# ==========================================
# УПРАВЛЕНИЕ БЭКАПАМИ
# ==========================================

@app.route('/backups')
@login_required
def backups():
    backup_list = []
    
    if os.path.exists(BACKUP_DIR):
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.tar.gz'):
                file_path = os.path.join(BACKUP_DIR, filename)
                stat = os.stat(file_path)
                backup_list.append({
                    'name': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).strftime('%d.%m.%Y %H:%M'),
                    'size_mb': round(stat.st_size / (1024 * 1024), 2)
                })
    
    backup_list.sort(key=lambda x: x['created'], reverse=True)
    
    return render_template('backups.html', backups=backup_list)

@app.route('/backups/download/<filename>')
@login_required
def download_backup(filename):
    if '..' in filename or '/' in filename:
        flash('Недопустимое имя файла', 'danger')
        return redirect(url_for('backups'))
    
    file_path = os.path.join(BACKUP_DIR, filename)
    
    if not os.path.abspath(file_path).startswith(os.path.abspath(BACKUP_DIR)):
        flash('Попытка выхода за пределы директории', 'danger')
        return redirect(url_for('backups'))
    
    if os.path.exists(file_path):
        audit_logger.info(f"ACTION:BACKUP_DOWNLOAD | ADMIN:WEB | FILE:{filename}")
        return send_file(file_path, as_attachment=True)
    else:
        flash('Файл не найден', 'danger')
        return redirect(url_for('backups'))

@app.route('/backups/create', methods=['POST'])
@login_required
def create_backup():
    import subprocess
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"manual_backup_{timestamp}.tar.gz"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        result = subprocess.run([
            'tar', '-czf', backup_path,
            '-C', '/opt/durdom-bot',
            'bot_data', 'handlers', 'utils', 'keyboards', 'states', 'database',
            'config.py', 'main.py', '.env'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            audit_logger.info(f"ACTION:BACKUP_CREATE | ADMIN:WEB | FILE:{backup_name}")
            flash(f'Бэкап создан: {backup_name}', 'success')
        else:
            flash(f'Ошибка создания бэкапа: {result.stderr}', 'danger')
    except Exception as e:
        flash(f'Ошибка: {e}', 'danger')
    
    return redirect(url_for('backups'))

# ==========================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ==========================================

@app.route('/users')
@login_required
def users():
    stats = load_json('bot_data/stats.json', {})
    user_proxies = load_json(USER_PROXIES_FILE, {})
    
    users_list = []
    for uid, data in stats.items():
        vpn_count = 0
        user_dir = os.path.join(VPN_DIR, data.get('username', ''))
        if os.path.exists(user_dir):
            vpn_count = len([f for f in os.listdir(user_dir) if f.endswith('.vpn')])
        
        proxy_count = len(user_proxies.get(uid, {}).get('proxies', []))
        
        users_list.append({
            'id': uid,
            'username': data.get('username', 'Unknown'),
            'name': data.get('name', ''),
            'total_actions': sum(data.get('actions', {}).values()),
            'vpn_count': vpn_count,
            'proxy_count': proxy_count,
            'is_admin': int(uid) in ADMIN_IDS
        })
    
    users_list.sort(key=lambda x: x['total_actions'], reverse=True)
    
    return render_template('users.html', users=users_list)

# ==========================================
# ПРОСМОТР ЛОГОВ
# ==========================================

@app.route('/logs')
@login_required
def logs():
    bot_log_path = 'bot_data/logs/bot.log'
    audit_log_path = 'bot_data/logs/audit.log'
    
    bot_logs = []
    if os.path.exists(bot_log_path):
        with open(bot_log_path, 'r', encoding='utf-8') as f:
            bot_logs = f.readlines()
    
    audit_logs = []
    if os.path.exists(audit_log_path):
        with open(audit_log_path, 'r', encoding='utf-8') as f:
            audit_logs = f.readlines()
    
    return render_template('logs.html', bot_logs=bot_logs, audit_logs=audit_logs)

@app.route('/logs/stream')
@login_required
def log_stream():
    """Real-time логи через Server-Sent Events"""
    def generate():
        bot_log_path = 'bot_data/logs/bot.log'
        last_pos = 0
        if os.path.exists(bot_log_path):
            last_pos = os.path.getsize(bot_log_path)
        
        while True:
            if os.path.exists(bot_log_path):
                with open(bot_log_path, 'r', encoding='utf-8') as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()
                    
                    for line in new_lines:
                        yield f"data: {line.strip()}\n\n"
            
            time.sleep(1)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/logs/audit-stream')
@login_required
def audit_log_stream():
    """Real-time audit логи"""
    def generate():
        audit_log_path = 'bot_data/logs/audit.log'
        last_pos = 0
        if os.path.exists(audit_log_path):
            last_pos = os.path.getsize(audit_log_path)
        
        while True:
            if os.path.exists(audit_log_path):
                with open(audit_log_path, 'r', encoding='utf-8') as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    last_pos = f.tell()
                    
                    for line in new_lines:
                        yield f"data: {line.strip()}\n\n"
            
            time.sleep(1)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/logs/clear', methods=['POST'])
@login_required
def clear_logs():
    log_type = request.form.get('log_type')
    
    if log_type == 'bot':
        log_path = 'bot_data/logs/bot.log'
    elif log_type == 'audit':
        log_path = 'bot_data/logs/audit.log'
    else:
        flash('Неверный тип лога', 'danger')
        return redirect(url_for('logs'))
    
    if os.path.exists(log_path):
        with open(log_path, 'w') as f:
            f.write('')
        audit_logger.info(f"ACTION:LOG_CLEAR | ADMIN:WEB | LOG:{log_type}")
        flash(f'Лог {log_type} очищен', 'success')
    else:
        flash('Файл лога не найден', 'danger')
    
    return redirect(url_for('logs'))

# ==========================================
# ЖУРНАЛ ВХОДОВ
# ==========================================

@app.route('/logins')
@login_required
def logins():
    logins_list = load_json(login_history_file, [])
    logins_list.reverse()
    return render_template('logins.html', logins=logins_list)

# ==========================================
# НАСТРОЙКИ
# ==========================================

@app.route('/settings')
@login_required
def settings():
    env_content = ENV_VARS.copy()
    
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    return render_template('settings.html', 
                          env_content=env_content,
                          python_version=python_version,
                          bot_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          vpn_path=VPN_DIR,
                          backup_path=BACKUP_DIR)

# ==========================================
# API ENDPOINTS
# ==========================================

@app.route('/api/stats')
@login_required
def api_stats():
    stats = load_json('bot_data/stats.json', {})
    vpn_expired, vpn_expiring = check_all_vpn_expiry()
    proxy_expired, proxy_expiring = check_all_proxy_expiry()
    
    return jsonify({
        'total_users': len(stats),
        'vpn_expired': len(vpn_expired),
        'vpn_expiring': len(vpn_expiring),
        'proxy_expired': len(proxy_expired),
        'proxy_expiring': len(proxy_expiring),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/system')
@login_required
def api_system():
    return jsonify({
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent,
        'uptime': str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0]
    })

# ==========================================
# ОБРАБОТЧИК ОШИБОК
# ==========================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('login.html'), 404

@app.errorhandler(500)
def internal_error(e):
    audit_logger.error(f"ACTION:WEB_500_ERROR | ERROR:{e}")
    return "Внутренняя ошибка сервера", 500

# ==========================================
# ЗАПУСК
# ==========================================

if __name__ == '__main__':
    port = int(ENV_VARS.get('WEB_PORT', 5050))
    
    standard_logger.info(f"🌐 Веб-интерфейс запускается на порту {port}")
    audit_logger.info(f"ACTION:WEB_START | PORT:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)