# PyWebIO组件/PyWebIO components
import os
import threading
import time
import requests
import yaml
from pywebio import session, config as pywebio_config
from pywebio.input import *
from pywebio.output import *
from pywebio.session import register_thread

from app.web.views.About import about_pop_window
from app.web.views.Document import api_document_pop_window
from app.web.views.Downloader import downloader_pop_window
from app.web.views.EasterEgg import a
from app.web.views.ParseVideo import parse_video
from app.web.views.Shortcuts import ios_pop_window
# PyWebIO的各个视图/Views of PyWebIO
from app.web.views.ViewsUtils import ViewsUtils

# 读取上级再上级目录的配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    _config = yaml.safe_load(file)

pywebio_config(theme=_config['Web']['PyWebIO_Theme'],
               title=_config['Web']['Tab_Title'],
               description=_config['Web']['Description'],
               js_file=[
                   # 整一个看板娘，二次元浓度++
                   _config['Web']['Live2D_JS'] if _config['Web']['Live2D_Enable'] else None,
               ])


class MainView:
    def __init__(self):
        self.utils = ViewsUtils()

    # 主界面/Main view
    def main_view(self):
        # 左侧导航栏/Left navbar
        with use_scope('main'):
            # 设置favicon/Set favicon
            favicon_url = _config['Web']['Favicon']
            session.run_js(f"""
                            $('head').append('<link rel="icon" type="image/png" href="{favicon_url}">')
                            """)
            # 修改footer/Remove footer
            session.run_js("""$('footer').remove()""")
            # 设置不允许referrer/Set no referrer
            session.run_js("""$('head').append('<meta name=referrer content=no-referrer>');""")
            # 设置标题/Set title
            title = self.utils.t("TikTok/抖音无水印在线解析下载",
                                 "Douyin/TikTok online parsing and download without watermark")
            put_html(f"""
                    <div align="center">
                    <a href="/" alt="logo" ><img src="{favicon_url}" width="100"/></a>
                    <h1 align="center">{title}</h1>
                    </div>
                    """)
            # 设置导航栏/Navbar
            put_row(
                [
                    put_button(self.utils.t("快捷指令", 'iOS Shortcut'),
                               onclick=lambda: ios_pop_window(), link_style=True, small=True),
                    put_button(self.utils.t("开放接口", 'Open API'),
                               onclick=lambda: api_document_pop_window(), link_style=True, small=True),
                    put_button(self.utils.t("下载器", "Downloader"),
                               onclick=lambda: downloader_pop_window(), link_style=True, small=True),
                    put_button(self.utils.t("关于", 'About'),
                               onclick=lambda: about_pop_window(), link_style=True, small=True),
                ])

            # 设置功能选择/Function selection
            options = [
                # Index: 0
                self.utils.t('🔍批量解析视频', '🔍Batch Parse Video'),
                # Index: 1
                self.utils.t('🔍解析用户主页视频', '🔍Parse User Homepage Video'),
                # Index: 2
                self.utils.t('🥚小彩蛋', '🥚Easter Egg'),
            ]
            
            def render_tasks_table(open_collapse=False):
                try:
                    # 获取任务列表
                    host_ip = _config['API']['Host_IP']
                    host_port = _config['API']['Host_Port']
                    if host_ip == '0.0.0.0':
                        host_ip = '127.0.0.1'
                    
                    api_url = f"http://{host_ip}:{host_port}/api/download/tasks"
                    
                    response = requests.get(api_url, timeout=2)
                    if response.status_code == 200:
                        tasks = response.json()
                        # 即使没有任务也显示表格框架，或者显示无任务提示
                        
                        table_data = [['Task ID', 'Filename', 'Status', 'Platform', 'Created At', 'Action']]
                        if tasks:
                            # 按时间倒序
                            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                            
                            for task in tasks:
                                meta = task.get('meta', {})
                                task_id = task.get('id')
                                saved_path = task.get('saved_path')
                                
                                if saved_path:
                                    filename = os.path.basename(saved_path)
                                else:
                                    filename = meta.get('custom_name') or f"{meta.get('platform')}_{meta.get('video_id')}"
                                
                                # 创建查看详情的按钮
                                def show_detail(tid=task_id):
                                    try:
                                        detail_url = f"http://{host_ip}:{host_port}/api/download/task/{tid}"
                                        res = requests.get(detail_url, timeout=2)
                                        if res.status_code == 200:
                                            task_detail = res.json()
                                            popup(self.utils.t('任务详情', 'Task Detail'), [
                                                put_code(yaml.dump(task_detail, allow_unicode=True), language='yaml')
                                            ])
                                    except Exception as e:
                                        toast(f"Error: {e}", color='error')

                                table_data.append([
                                    task_id[:8] + '...',
                                    filename,
                                    task.get('status'),
                                    meta.get('platform', 'Unknown'),
                                    task.get('created_at'),
                                    put_button("Detail", onclick=show_detail, small=True)
                                ])
                        
                        with use_scope('task_status_scope', clear=True):
                            put_collapse(self.utils.t('下载任务状态', 'Download Task Status'), [
                                put_button(self.utils.t('刷新', 'Refresh'), onclick=lambda: render_tasks_table(True), small=True, outline=True),
                                put_table(table_data)
                            ], open=open_collapse)
                except Exception as e:
                    # toast(f"Error loading tasks: {e}", color='error')
                    pass

            # 将刷新函数注册到 session.local，以便其他模块调用
            # 传入 True 以便在刷新时自动展开
            session.local['refresh_task_table'] = lambda: render_tasks_table(open_collapse=True)

            def init_tasks_table():
                # 延迟一点时间，确保 select 组件已经渲染
                time.sleep(0.5)
                # 创建scope
                put_scope('task_status_scope')
                render_tasks_table()

            # 启动后台线程显示表格
            t = threading.Thread(target=init_tasks_table)
            register_thread(t)
            t.start()

            select_options = select(
                self.utils.t('请在这里选择一个你想要的功能吧 ~', 'Please select a function you want here ~'),
                required=True,
                options=options,
                help_text=self.utils.t('📎选上面的选项然后点击提交', '📎Select the options above and click Submit')
            )

            # 根据输入运行不同的函数
            if select_options == options[0]:
                parse_video()
            elif select_options == options[1]:
                put_markdown(self.utils.t('暂未开放，敬请期待~', 'Not yet open, please look forward to it~'))
            elif select_options == options[2]:
                a() if _config['Web']['Easter_Egg'] else put_markdown(self.utils.t('没有小彩蛋哦~', 'No Easter Egg~'))
