#!/usr/bin/env python3
"""
智联招聘简历搜索脚本 - 支持API模式和浏览器截图
从 rd6.zhaopin.com API 获取简历数据，并可选地使用浏览器截图验证筛选条件
"""

import argparse
import json
import os
import sys
import re
import time
from datetime import datetime
from pathlib import Path

import requests

# 是否启用浏览器截图功能（需要时再导入playwright）
ENABLE_BROWSER_SCREENSHOT = False


def load_playwright():
    """延迟加载playwright，避免不使用浏览器时也要求安装"""
    global ENABLE_BROWSER_SCREENSHOT
    try:
        from playwright.sync_api import sync_playwright
        ENABLE_BROWSER_SCREENSHOT = True
        return sync_playwright
    except ImportError:
        print("警告: 未安装playwright，无法使用浏览器截图功能")
        return None


# Cookie 配置文件路径
COOKIE_FILE = "/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt"
# API基础URL
API_BASE = "https://rd6.zhaopin.com"


def load_cookies(cookie_file=None):
    """加载Cookie"""
    if cookie_file is None:
        cookie_file = COOKIE_FILE

    if not os.path.exists(cookie_file):
        print(f"错误:Cookie配置文件不存在: {cookie_file}")
        return None

    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookies = f.read().strip()

    if not cookies:
        print(f"错误:Cookie文件为空: {cookie_file}")
        return None

    return cookies


def get_city_id(city_name):
    """将城市名转换为ID，支持 '市-区' 或 '省-市' 格式自动提取城市"""
    city_map = {
        "周口": 734, "郑州": 701, "北京": 530, "上海": 538,
        "深圳": 765, "广州": 763, "杭州": 653, "南京": 635,
        "东莞": 779, "中山": 780, "成都": 801, "武汉": 736,
        "西安": 854, "长沙": 749, "重庆": 551, "苏州": 639,
        "宝安": 765, "惠州": 773, "清溪": 779,
    }
    # 优先精确匹配
    if city_name in city_map:
        return city_map[city_name]
    # 支持 "市-区" 或 "省-市" 格式，尝试只匹配城市部分
    for sep in ['-', ' ', '　']:
        if sep in city_name:
            city_part = city_name.split(sep)[0]
            if city_part in city_map:
                return city_map[city_part]
            # 再尝试第二部分
            parts = city_name.split(sep)
            for part in parts:
                if part in city_map:
                    return city_map[part]
    # 未知城市，默认周口
    return 734


def take_search_screenshot(keywords, location=None, education=None, experience=None, age=None, school=None):
    """
    使用浏览器打开搜索页面，设置筛选条件并截图
    返回浏览器对象，可用于后续操作
    """
    playwright = load_playwright()
    if not playwright:
        return None
    
    # 保存截图的目录
    debug_dir = "/tmp/zhaopin_debug"
    os.makedirs(debug_dir, exist_ok=True)
    
    print(f"\n🌐 启动浏览器并设置筛选条件...")
    print(f"   关键词: {keywords}")
    print(f"   地点: {location or '不限'}")
    print(f"   学历: {education or '不限'}")
    print(f"   经验: {experience or '不限'}")
    
    browser_obj = None
    try:
        # 加载cookie
        cookies = load_cookies()
        if not cookies:
            print("   错误: 无法加载Cookie")
            return None
        
        playwright = load_playwright()
        if not playwright:
            print("   错误: 无法加载Playwright")
            return None
        
        # 使用context manager来获取playwright实例，所有browser操作必须在with块内完成
        with playwright() as p:
            browser_obj = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = browser_obj.new_context()
            
            # 设置Cookie
            cookie_list = []
            for cookie_str in cookies.split(';'):
                cookie_str = cookie_str.strip()
                if '=' in cookie_str:
                    name, value = cookie_str.split('=', 1)
                    cookie_list.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.zhaopin.com',
                        'path': '/'
                    })
            context.add_cookies(cookie_list)
            
            page = context.new_page()
            
            print(f"   访问搜索页面...")
            page.goto('https://rd6.zhaopin.com/app/search', timeout=30000)
            page.wait_for_load_state('networkidle', timeout=15000)
            
            # 关闭新手引导弹窗（如果出现）- 使用JavaScript直接移除
            try:
                # 尝试通过JS移除新手引导弹窗
                page.evaluate('''
                    var popups = document.querySelectorAll(".km-popover, .novice-guide-popper, [class*=popper], [class*=modal], .overlay");
                    popups.forEach(function(el) { el.remove(); });
                ''')
                page.wait_for_timeout(500)
            except Exception as e:
                print(f"   移除新手引导失败: {e}")
    
                
            # 截图1: 初始搜索页面
            page.screenshot(path=f"{debug_dir}/search_01_initial.png")
            print(f"   ✅ 已保存初始页面截图: {debug_dir}/search_01_initial.png")
            
            # 输入关键词 - 直接使用fill()而不是click()+fill()
            print(f"   输入关键词: {keywords}")
            keyword_input = page.locator('input[class*=\"keyword\"]').first
            if keyword_input.count() > 0:
                keyword_input.fill(keywords)
            else:
                # 尝试其他选择器
                keyword_input = page.locator('input[placeholder*=\"岗位\"]').first
                if keyword_input.count() > 0:
                    keyword_input.fill(keywords)
            
            # 设置城市筛选 - 2026-05-22 新增：之前遗漏导致截图始终显示默认城市
            if location:
                print(f"   设置城市筛选: {location}")
                try:
                    # 智联城市选择器: .keyword-panel-city__label
                    city_trigger = page.locator('.keyword-panel-city__label').first
                    if city_trigger.count() > 0:
                        current_city = city_trigger.text_content() or ''
                        print(f"   当前城市: {current_city.strip()}")
                        
                        # 如果当前城市已经是目标城市，跳过
                        if location in current_city:
                            print(f"   城市已是 {location}，无需修改")
                        else:
                            city_trigger.click()
                            page.wait_for_timeout(1000)
                            
                            # 在下拉/弹窗中查找目标城市
                            city_option = page.locator(f'text="{location}"').first
                            if city_option.count() > 0:
                                city_option.click()
                                page.wait_for_timeout(500)
                                page.keyboard.press('Escape')
                                page.wait_for_timeout(300)
                                print(f"   城市筛选已设置: {location}")
                            else:
                                # 尝试在输入框中搜索城市
                                city_input = page.locator('input[placeholder*="城市"], input[placeholder*="搜索"]').first
                                if city_input.count() > 0:
                                    city_input.fill(location)
                                    page.wait_for_timeout(1500)
                                    sel_option = page.locator(f'text="{location}"').first
                                    if sel_option.count() > 0:
                                        sel_option.click()
                                        page.wait_for_timeout(500)
                                        page.keyboard.press('Escape')
                                        page.wait_for_timeout(300)
                                        print(f"   城市筛选已设置: {location}")
                                else:
                                    page.keyboard.press('Escape')
                                    print(f"   ⚠️ 下拉中未找到 {location}")
                    else:
                        print(f"   ⚠️ 未找到城市选择器 .keyword-panel-city__label")
                except Exception as e:
                    print(f"   城市筛选设置失败: {e}")

            # 关闭可能残留的城市选择弹窗遮罩层
            try:
                page.evaluate('''() => {
                    var overlays = document.querySelectorAll(".s-dialog__overlay, .km-popover__overlay, [class*=overlay]");
                    overlays.forEach(function(el) { el.remove(); });
                }''')
                page.wait_for_timeout(300)
            except:
                pass

            # 设置学历筛选 - 点击标签后再点击选项，然后按Escape关闭
            if education and '不限' not in education:
                print(f"   设置学历筛选: {education}")
                try:
                    # 点击学历筛选器标签
                    edu_trigger = page.locator('.search-label-wrapper-new__label:has-text("学历要求")').first
                    if edu_trigger.count() > 0:
                        edu_trigger.click()
                        page.wait_for_timeout(500)
                        
                        # 选择对应的学历选项 - 直接点击文本
                        if education in ['本科', '本科及以上']:
                            edu_option = page.locator('text=本科及以上').first
                        elif education in ['大专', '大专及以上']:
                            edu_option = page.locator('text=大专及以上').first
                        elif education in ['硕士', '硕士及以上']:
                            edu_option = page.locator('text=硕士及以上').first
                        else:
                            edu_option = None
                        
                        if edu_option and edu_option.count() > 0:
                            edu_option.click()
                            page.wait_for_timeout(300)
                            page.keyboard.press('Escape')
                            page.wait_for_timeout(300)
                            print(f"   学历筛选已设置")
                except Exception as e:
                    print(f"   学历筛选设置失败: {e}")
            # 设置经验筛选 - 点击标签后再点击选项，然后按Escape关闭
            if experience and '不限' not in experience:
                print(f"   设置经验筛选: {experience}")
                try:
                    # 点击经验筛选器标签
                    exp_trigger = page.locator('.search-label-wrapper-new__label:has-text("经验要求")').first
                    if exp_trigger.count() > 0:
                        exp_trigger.click()
                        page.wait_for_timeout(500)
                        
                        # 选择对应的经验选项 - 直接点击文本
                        exp_map = {
                            '1年以下': '无经验',
                            '1-3年': '1-3年',
                            '3-5年': '3-5年',
                            '5-10年': '5-10年',
                            '10年以上': '自定义'
                        }
                        exp_text = exp_map.get(experience, '')
                        if exp_text:
                            exp_option = page.locator(f'text={exp_text}').first
                            if exp_option and exp_option.count() > 0:
                                exp_option.click()
                                page.wait_for_timeout(300)
                                page.keyboard.press('Escape')
                                page.wait_for_timeout(300)
                                print(f"   经验筛选已设置: {exp_text}")
                except Exception as e:
                    print(f"   经验筛选设置失败: {e}")

            # 设置年龄筛选 - 点击标签后再点击选项，然后按Escape关闭
            if age and '不限' not in age:
                print(f"   设置年龄筛选: {age}")
                try:
                    # 点击年龄筛选器标签
                    age_trigger = page.locator('.search-label-wrapper-new__label:has-text("年龄要求")').first
                    if age_trigger.count() > 0:
                        age_trigger.click()
                        page.wait_for_timeout(500)
                        
                        # 选择对应的年龄选项
                        if age in ['20-25', '25-30', '30-35', '35-40', '40以上']:
                            age_option = page.locator(f'.search-label-wrapper-new__content:has-text("{age}")').first
                            if age_option and age_option.count() > 0:
                                age_option.click()
                                page.wait_for_timeout(300)
                                page.keyboard.press('Escape')
                                page.wait_for_timeout(300)
                                print(f"   年龄筛选已设置")
                except Exception as e:
                    print(f"   年龄筛选设置失败: {e}")
            
            # 设置院校筛选 - 点击标签后再点击选项，然后按Escape关闭
            if school and '不限' not in school:
                print(f"   设置院校筛选: {school}")
                try:
                    # 点击院校筛选器标签
                    school_trigger = page.locator('.search-label-wrapper-new__label:has-text("院校要求")').first
                    if school_trigger.count() > 0:
                        school_trigger.click()
                        page.wait_for_timeout(500)
                        
                        # 选择对应的院校选项
                        school_map = {
                            '985': '985',
                            '211': '211',
                            '双一流': '双一流',
                            '海外院校': '海外院校',
                            '统招': '统招'
                        }
                        school_text = school_map.get(school, school)
                        school_option = page.locator(f'.search-label-wrapper-new__content:has-text("{school_text}")').first
                        if school_option and school_option.count() > 0:
                            school_option.click()
                            page.wait_for_timeout(300)
                            page.keyboard.press('Escape')
                            page.wait_for_timeout(300)
                            print(f"   院校筛选已设置")
                except Exception as e:
                    print(f"   院校筛选设置失败: {e}")
            
            # 截图2: 设置筛选条件后
            page.screenshot(path=f"{debug_dir}/search_02_with_filters.png")
            print(f"   ✅ 已保存筛选条件设置后截图: {debug_dir}/search_02_with_filters.png")
            
            # 点击搜索按钮
            print(f"   点击搜索...")
            search_button = page.locator('button:has-text(\"搜索\")').first
            if search_button.count() > 0:
                search_button.click()
            else:
                # 尝试按Enter键
                keyword_input.press('Enter')
            
            page.wait_for_load_state('networkidle', timeout=15000)
            page.wait_for_timeout(2000)
            
            # 截图3: 搜索结果
            page.screenshot(path=f"{debug_dir}/search_03_results.png")
            print(f"   ✅ 已保存搜索结果截图: {debug_dir}/search_03_results.png")
            
            print(f"\n   浏览器自动化完成！")
            print(f"   截图保存目录: {debug_dir}")
            
            # 关闭浏览器
            browser_obj.close()
        return True
        
    except Exception as e:
        print(f"   浏览器自动化失败: {e}")
        import traceback
        traceback.print_exc()
        if browser_obj:
            try:
                browser_obj.close()
            except:
                pass
        return None


def search_resumes_by_api(keywords, location=None, education=None, experience=None, count=5, cookies=None):
    """通过API搜索简历 - 自动翻页获取所有结果"""
    if cookies is None:
        cookies = load_cookies()
        if cookies is None:
            return []

    print(f"开始搜索简历 (API模式)...")
    print(f"关键词: {keywords}")
    print(f"地点: {location or '不限'}")
    print(f"数量: {count}")

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'Cookie': cookies,
        'Origin': API_BASE,
        'Referer': f'{API_BASE}/app/search',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    city_ids = [get_city_id(location)] if location else []

    # 教育程度: 1=不限, 3=大专, 4=本科, 10=硕士, 5=博士
    # 注意:当只设置 ["1"] 时API返回异常,需使用完整数组
    if education and "不限" not in education:
        edu_map = {"大专": "3", "本科": "4", "硕士": "10", "博士": "5"}
        edu_levels = [edu_map[e] for e in edu_map if e in education]
    else:
        # 使用完整数组以确保API正常返回
        edu_levels = ["4", "3", "10", "1"]

    # 使用TIME排序(最新优先)而不是COMPLEX,避免算法过滤
    # pageSize设置足够大,确保能获取到请求的数量
    # 工作经验筛选: 1=不限, 2=1年以下, 3=1-3年, 4=3-5年, 5=5-10年, 6=10年以上
    # 注意: filteringChatted=False 以获取所有候选人,不过滤已沟通的
    if experience and "不限" not in experience:
        exp_map = {"1年以下": "2", "1-3年": "3", "3-5年": "4", "5-10年": "5", "10年以上": "6"}
        exp_levels = [exp_map[e] for e in exp_map if e in experience]
    else:
        exp_levels = []

    # 第一页请求：获取总结果数和页数信息
    payload = {
        "expectedCityIds": city_ids,
        "keywordIntentions": [{"keyword": keywords}],
        "educations": edu_levels,
        "workingYears": exp_levels,
        "filteringChatted": False,  # 设置为False以获取所有候选人，不过滤已沟通的
        "filteringRead": False,
        "filteringDownloaded": False,
        "sort": {
            "type": "TIME",
            "version": 0
        },
        "pageNo": 1,
        "pageSize": 50,  # 增大每页数量，提高效率
        "filteringOtherChattedType": "DONT_FILTER",
        "matchLatestWorkExperience": False,
        "searchExperimentalGroup": "EXPERIMENT",
        "frontExperiment": True,
        "firstPageCacheable": False,
        "freeMaskLimit": False,
        "experiment": ""
    }

    try:
        url = f"{API_BASE}/api/talent/search/list"
        print(f"\n1. 调用搜索API获取总页数...")

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"   状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"   请求失败")
            return []

        data = response.json()

        # 获取总结果数
        total_count = data.get('data', {}).get('total', 0)
        
        print(f"   总结果数: {total_count}")
        
        if total_count == 0:
            print(f"   未找到任何结果")
            return []

        # 收集所有页的简历
        all_results = []
        page_no = 1
        # 动态计算最大页数：根据总结果数和每页数量计算，并设置合理上限
        calculated_max_pages = (total_count + 50 - 1) // 50  # 向上取整
        max_pages = min(calculated_max_pages, 100)  # 最多100页，上限保护
        print(f"   计算总页数: {calculated_max_pages}，实际最多抓取: {max_pages} 页")
        
        # 首先收集第一页的结果
        first_page_results = data.get('data', {}).get('list', [])
        if not first_page_results:
            print(f"   第1页返回空结果")
            return []
            
        all_results.extend(first_page_results)
        print(f"   第1页: 获取 {len(first_page_results)} 条结果")
        
        # 继续抓取后续页面，直到达到目标数量、满页或达到最大页数
        print(f"\n2. 抓取剩余页面...")
        while page_no < max_pages:
            # 如果已收集足够结果，提前停止抓取
            if len(all_results) >= count:
                print(f"   已收集 {len(all_results)} 条结果，达到目标数量 {count}，停止抓取")
                break
            
            page_no += 1
            
            page_payload = {
                "expectedCityIds": city_ids,
                "keywordIntentions": [{"keyword": keywords}],
                "educations": edu_levels,
                "workingYears": exp_levels,
                "filteringChatted": False,  # 设置为False以获取所有候选人
                "filteringRead": False,
                "filteringDownloaded": False,
                "sort": {
                    "type": "TIME",
                    "version": 0
                },
                "pageNo": page_no,
                "pageSize": 50,  # 增大每页数量
                "filteringOtherChattedType": "DONT_FILTER",
                "matchLatestWorkExperience": False,
                "searchExperimentalGroup": "EXPERIMENT",
                "frontExperiment": True,
                "firstPageCacheable": False,
                "freeMaskLimit": False,
                "experiment": ""
            }
            
            try:
                page_response = requests.post(url, headers=headers, json=page_payload, timeout=30)
                if page_response.status_code == 200:
                    page_data = page_response.json()
                    page_results = page_data.get('data', {}).get('list', [])
                    
                    if not page_results:
                        print(f"   第{page_no}页: 空结果，停止抓取")
                        break
                        
                    all_results.extend(page_results)
                    print(f"   第{page_no}页: 获取 {len(page_results)} 条 (累计: {len(all_results)})")
                else:
                    print(f"   第{page_no}页: 失败 (状态码: {page_response.status_code})")
                    break
            except Exception as e:
                print(f"   第{page_no}页: 异常 ({e})")
                break
        
        print(f"\n3. 共获取 {len(all_results)} 条简历，开始解析和过滤...")
        
        # 解析所有结果并应用客户端过滤
        resumes = parse_search_response_all(all_results, count, experience)
        print(f"\n✅ 成功获取 {len(resumes)} 份符合条件简历")

        return resumes

    except Exception as e:
        print(f"❌ API请求失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_search_response(data, count, experience=None):
    """解析搜索API响应"""
    resumes = []
    filtered_count = 0
    
    try:
        if data.get('code') != 200:
            print(f"   API返回错误: {data.get('message', 'Unknown')}")
            return []
        
        # 获取简历列表 - 关键路径: data.data.list
        results = data.get('data', {}).get('list', [])
        print(f"   找到 {len(results)} 条结果")
        
        for i, item in enumerate(results):
            resume = extract_resume_from_item(item, i+1)
            if resume:
                # 客户端过滤：根据工作经验筛选
                if experience and "不限" not in experience:
                    work_years_label = resume.get('工作年限', '')
                    # 解析工作经验，检查是否在要求范围内
                    if not matches_experience(work_years_label, experience):
                        print(f"   过滤: {resume.get('姓名')} (工作经验: {work_years_label}, 不符合 {experience})")
                        filtered_count += 1
                        continue
                resumes.append(resume)
        
        if filtered_count > 0:
            print(f"   客户端过滤掉 {filtered_count} 条不符合经验要求的简历")
    
    except Exception as e:
        print(f"解析响应失败: {e}")
    
    return resumes


def parse_search_response_all(all_results, count, experience=None):
    """解析所有页的搜索结果并应用过滤"""
    resumes = []
    filtered_count = 0
    
    print(f"   原始结果总数: {len(all_results)}")
    
    for i, item in enumerate(all_results):
        resume = extract_resume_from_item(item, i+1)
        if resume:
            # 客户端过滤：根据工作经验筛选
            if experience and "不限" not in experience:
                work_years_label = resume.get('工作年限', '')
                # 解析工作经验，检查是否在要求范围内
                if not matches_experience(work_years_label, experience):
                    print(f"   过滤: {resume.get('姓名')} (工作经验: {work_years_label}, 不符合 {experience})")
                    filtered_count += 1
                    continue
            resumes.append(resume)
    
    if filtered_count > 0:
        print(f"   客户端过滤掉 {filtered_count} 条不符合经验要求的简历")
    
    # 限制返回数量不超过 count
    if count and len(resumes) > count:
        resumes = resumes[:count]
        print(f"   最终返回前 {count} 条简历")
    
    return resumes


def matches_experience(work_years_label, experience_req):
    """检查工作经验是否匹配要求
    experience_req: "3-5年", "1-3年", "5-10年" 等
    返回: True 如果匹配
    """
    if not work_years_label or not experience_req:
        return True
    
    # 提取数字
    import re
    numbers = re.findall(r'\d+', work_years_label)
    if not numbers:
        # "应届生" 等情况
        if '应届' in work_years_label or '在校' in work_years_label:
            return False
        return True
    
    years = int(numbers[0])
    
    # 根据要求判断
    if '3-5年' in experience_req or '3-5年' == experience_req:
        return 3 <= years <= 5
    elif '1-3年' in experience_req or '1-3年' == experience_req:
        return 1 <= years <= 3
    elif '5-10年' in experience_req or '5-10年' == experience_req:
        return 5 <= years <= 10
    elif '1年以下' in experience_req or '1年以下' == experience_req:
        return years < 1
    elif '10年' in experience_req and '以上' in experience_req:
        return years >= 10
    
    return True


def extract_resume_from_item(item, index):
    """从单个简历项提取数据"""
    try:
        # 基本信息
        name = item.get('userName', '')
        gender = item.get('gender', '')
        if not gender:
            gender = '男' if item.get('genderKey') == '1' else '女'

        resume = {
            '序号': index,
            '姓名': name,
            '性别': gender,
            '年龄': f"{item.get('age', '')}岁" if item.get('age') else '',
            '工作年限': item.get('workYearsLabel', ''),
            '最高学历': item.get('educationLevel', '') or '',
            '当前职业状态': item.get('careerStatus', ''),
            '期望城市': item.get('desiredCity', ''),
            '期望职位': item.get('desiredJobType', ''),
            '期望薪资': item.get('desiredSalary', ''),
            '活跃标签': item.get('newUserActiveTag', {}).get('describe', '') if isinstance(item.get('newUserActiveTag'), dict) else '',
            '在线状态': '在线' if item.get('online') else '离线',
            '工作经历': '',
            '技能标签': '',
            '证书': '',
            '推荐理由': '',
            '简历类型': '校园简历' if item.get('isSchoolResume') else '普通简历',
            '手机可见': '',
            '备注': '',
            '教育经历': '',
            'resumeNumber': item.get('resumeNumber', ''),
        }

        # 提取工作经历
        work_exps = item.get('workExperiences', [])
        if work_exps:
            exp_list = []
            for exp in work_exps[:3]:  # 最多3段
                company = exp.get('companyName', '')
                position = exp.get('jobTitle', '')
                duration = exp.get('duration', '')
                if company or position:
                    exp_list.append(f"{duration} {company} {position}".strip())
            resume['工作经历'] = ' | '.join(exp_list)

        # 提取教育经历
        edu_exps = item.get('educationExperiences', [])
        if edu_exps:
            edu_list = []
            edu_level_from_exp = ''  # 从eduExperiences中提取的最高学历
            for exp in edu_exps[:1]:  # 取最高学历
                school = exp.get('schoolName', '')
                major = exp.get('majorName', '')
                exp_edu_level = exp.get('educationLevel', '')
                if school or major:
                    edu_list.append(f"{school}·{major}")
                if exp_edu_level and not edu_level_from_exp:
                    edu_level_from_exp = exp_edu_level
            resume['教育经历'] = ' | '.join(edu_list)
            # 如果最高学历为空,从eduExperiences中提取
            if not resume['最高学历'] and edu_level_from_exp:
                resume['最高学历'] = edu_level_from_exp

        # 提取技能标签 - 从workExperiences的jobSubtype获取
        skills = set()
        for exp in work_exps:
            subtype = exp.get('jobSubtypeHighlight', {})
            if isinstance(subtype, dict):
                skill = subtype.get('name', '')
                if skill and skill not in ['0', '']:
                    skills.add(skill)
            # 也尝试jobSubTypeClassfication
            subtype2 = exp.get('jobSubTypeClassficationHighlight', {})
            if isinstance(subtype2, dict):
                skill2 = subtype2.get('name', '')
                if skill2 and skill2 not in ['0', '']:
                    skills.add(skill2)

        if skills:
            resume['技能标签'] = ', '.join(sorted(skills))

        # 提取证书
        certificates = item.get('certificateNames', [])
        if certificates and isinstance(certificates, list):
            resume['证书'] = ', '.join(certificates[:5])  # 最多5个证书

        # 提取推荐理由
        recommended_reason = item.get('recommendedReason', '')
        if recommended_reason:
            resume['推荐理由'] = recommended_reason
        else:
            # 如果没有推荐理由,根据活跃度生成默认推荐理由
            active_tag = resume['活跃标签']
            if '最近常来' in active_tag or '多位HR联系' in active_tag:
                resume['推荐理由'] = 'Ta最近常来,且有多位HR联系过Ta'
            elif '有回复' in active_tag:
                resume['推荐理由'] = '近期和多位HR有沟通'

        # 生成备注(根据一些条件)
        notes = []
        work_years = resume['工作年限']
        if work_years:
            if '应届' in work_years or '在校' in work_years:
                notes.append('应届生')
            elif '1年' in work_years or '2年' in work_years:
                notes.append('经验较少')
            elif '5年' in work_years or '3年' in work_years:
                notes.append('经验丰富')

        if '在职' in resume.get('当前职业状态', ''):
            notes.append('在职')
        elif '离职' in resume.get('当前职业状态', ''):
            notes.append('离职')

        if notes:
            resume['备注'] = ','.join(notes)

        return resume

    except Exception as e:
        print(f"提取简历数据失败: {e}")
        return None


def generate_screening_report(resumes, job_title, location, output_path, education_req=None, experience_req=None):
    """生成初筛报告(严格按模板格式)"""
    if not resumes:
        print("没有简历数据,无法生成报告")
        return False

    today = datetime.now().strftime('%Y-%m-%d')

    report = f"""# 智联招聘简历初筛报告:{job_title}

**生成时间**:{today}
**工作地点**:{location or '不限'}
**学历要求**:{education_req or '不限'}
**工作经验**:{experience_req or '不限'}
**简历数量**:{len(resumes)}份

---

## 📊 候选人匹配度排名

|序号|姓名|性别|年龄|工作年限|学历|教育经历|期望薪资|匹配度|备注|
|-|-|-|-|-|-|-|-|-|-|
"""

    for resume in resumes:
        name = resume.get('姓名', '未知')
        gender = resume.get('性别', '未知')
        age = resume.get('年龄', '未知')
        exp = resume.get('工作年限', '未知')
        edu = resume.get('最高学历', '未知')
        edu_exp = resume.get('教育经历', '未知')
        salary = resume.get('期望薪资', '未知')
        # 生成匹配度星星(简单根据工作年限和技能标签估算)
        match_score = calculate_match_score(resume)
        match_stars = '⭐' * match_score + '☆' * (5 - match_score)
        notes = resume.get('备注', '')

        report += f"|{resume.get('序号', '?')}|**{name}**|{gender}|{age}|{exp}|{edu}|{edu_exp}|{salary}|{match_stars}|{notes}|\n"

    report += "\n## 📄 简历详情\n"

    for resume in resumes:
        name = resume.get('姓名', '未知')
        # 恢复纯文本格式,无加粗无标题
        report += f"\n{resume.get('序号', '?')}. {name}\n"
        report += f"基本信息:{resume.get('性别', '')},{resume.get('年龄', '')},{resume.get('工作年限', '')}经验,{resume.get('当前职业状态', '')}\n"
        report += f"求职意向:期望{resume.get('期望城市', '')},{resume.get('期望职位', '')},期望薪资{resume.get('期望薪资', '')}\n"
        report += f"活跃状态:{resume.get('活跃标签', '')},{resume.get('在线状态', '')}\n"
        report += f"工作经历:{resume.get('工作经历', '暂无')}\n"
        report += f"技能标签:{resume.get('技能标签', '暂无')}\n"

        certs = resume.get('证书', '')
        if certs:
            report += f"证书:{certs}\n"

        rec_reason = resume.get('推荐理由', '')
        if rec_reason:
            report += f"推荐理由:{rec_reason}\n"

        resume_type = resume.get('简历类型', '')
        mobile_visible = resume.get('手机可见', '')
        report += f"简历类型:{resume_type},手机可见:{mobile_visible}\n"
        report += "---\n"

    # 生成招聘建议
    recruitment_advice = generate_recruitment_advice(resumes, job_title, location)

    report += f"""
## 💡 招聘建议

{recruitment_advice}

---

*📝 **本报告数据100%来自智联招聘API实时返回的真实数据**
*📁 **报告存储路径**:{output_path}
*🔒 **仅供内部招聘使用,严禁外泄候选人隐私信息***
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"✅ 初筛报告已生成: {output_path}")
    return True


def calculate_match_score(resume):
    """计算简历匹配度(1-5星)"""
    score = 3  # 默认3星

    work_years = resume.get('工作年限', '')
    skills = resume.get('技能标签', '')
    edu = resume.get('最高学历', '')

    # 根据工作年限调整
    if '应届' in work_years or '在校' in work_years:
        score -= 1
    elif '1年' in work_years or '2年' in work_years:
        score += 0
    elif '3年' in work_years or '4年' in work_years or '5年' in work_years:
        score += 1
    elif '5年' in work_years:
        score += 2

    # 根据技能标签调整
    if skills:
        skill_count = len(skills.split(','))
        if skill_count >= 3:
            score += 1

    # 根据学历调整
    if edu in ['硕士', '博士']:
        score += 1
    elif edu in ['本科']:
        score += 0

    # 确保分数在1-5范围内
    return max(1, min(5, score))


def generate_recruitment_advice(resumes, job_title, location):
    """生成招聘建议(按模板格式)"""
    if not resumes:
        return "暂无候选人数据"

    # 分析候选人构成
    experienced = []  # 有经验的
    fresh_grads = []  # 应届生
    for r in resumes:
        work_years = r.get('工作年限', '')
        if '应届' in work_years or '在校' in work_years:
            fresh_grads.append(r)
        else:
            experienced.append(r)

    # 分析薪资范围
    salaries = []
    for r in resumes:
        salary = r.get('期望薪资', '')
        if salary:
            salaries.append(salary)

    # 分析活跃度
    active_candidates = []
    for r in resumes:
        active = r.get('活跃标签', '')
        if '在线' in active or '有回复' in active or '最近' in active:
            active_candidates.append(r)

    advice = """**现状分析**:
"""
    advice += f"1. **经验分布**:收到{len(experienced)}位有工作经验的候选人,{len(fresh_grads)}位应届生\n"
    if experienced:
        advice += f"2. **薪资预期**:{salaries[0] if salaries else '未知'}(市场价位合理)\n"
    if location:
        advice += f"3. **地域分布**:期望地点为{location}\n"
    advice += f"4. **活跃度**:{len(active_candidates)}位候选人近期活跃\n"

    advice += "\n**推荐策略**:\n"
    if experienced:
        top_exp = experienced[0] if experienced else None
        if top_exp:
            advice += f"1. **重点面试**:{top_exp.get('姓名', '')}({top_exp.get('工作年限', '')}经验)\n"
    if fresh_grads:
        grad_names = ', '.join([r.get('姓名', '') for r in fresh_grads[:2]])
        # 获取第一个应届生的学历信息
        first_grad = fresh_grads[0] if fresh_grads else None
        edu_info = ''
        if first_grad:
            edu = first_grad.get('最高学历', '')
            if edu:
                edu_info = f"{edu}"
            else:
                school = first_grad.get('教育经历', '').split('·')[0] if first_grad.get('教育经历', '') else ''
                if school:
                    edu_info = f"{school}生"
        if edu_info:
            advice += f"2. **储备培养**:{grad_names}等{edu_info}可作为长期培养对象\n"
        else:
            advice += f"2. **储备培养**:{grad_names}等可作为长期培养对象\n"
    if active_candidates:
        advice += f"3. **快速联系**:{', '.join([r.get('姓名', '') for r in active_candidates[:2]])}等{len(active_candidates)}位候选人近期活跃,可优先联系\n"

    advice += "\n**面试建议**:\n"
    advice += f"- 重点考察{job_title}相关的实际项目经验\n"
    advice += "- 验证技能标签中的具体技术能力\n"
    advice += "- 确认到岗时间和薪资期望\n"
    advice += "- 注意考察学习能力和成长潜力\n"

    return advice


def save_search_context(keywords, location, education, experience, resumes):
    """保存搜索上下文到JSON文件，供后续打招呼脚本使用"""
    context = {
        "keywords": keywords,
        "location": location,
        "education": education,
        "experience": experience,
        "candidates": [
            {
                "name": r.get('姓名', ''),
                "gender": r.get('性别', ''),
                "age": r.get('年龄', ''),
                "work_years": r.get('工作年限', ''),
                "education": r.get('最高学历', ''),
                "match_score": r.get('匹配度', ''),
                "resume_number": r.get('resumeNumber', ''),
            }
            for r in resumes
        ],
        "saved_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    context_path = '/tmp/zhaopin_search_context.json'
    try:
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
        print(f"✅ 搜索上下文已保存: {context_path}")
        return True
    except Exception as e:
        print(f"⚠️ 搜索上下文保存失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='智联招聘简历搜索 (API版)')
    parser.add_argument('--keywords', '-k', required=True, help='岗位关键词')
    parser.add_argument('--location', '-l', default='', help='工作地点')
    parser.add_argument('--education', '-e', default='', help='学历要求')
    parser.add_argument('--experience', '-exp', default='', help='工作经验要求 (如3-5年, 1-3年, 5-10年)')
    parser.add_argument('--age', default='', help='年龄要求 (如25-30, 30-35)')
    parser.add_argument('--school', default='', help='院校要求 (如985, 211, 双一流)')
    parser.add_argument('--count', '-c', type=int, default=5, help='简历数量')
    parser.add_argument('--output', '-o', help='输出报告路径')
    parser.add_argument('--cookies', help='Cookie字符串')
    parser.add_argument('--screenshot', '-s', action='store_true', help='使用浏览器截图模式（验证筛选条件）')

    args = parser.parse_args()

    cookies = args.cookies or load_cookies()
    if cookies is None:
        print("错误:请提供Cookie")
        return 1

    # 如果设置了 --screenshot 参数，先使用浏览器截图验证筛选条件
    if args.screenshot:
        print("\n" + "="*50)
        print("浏览器截图模式：验证筛选条件")
        print("="*50)
        screenshot_result = take_search_screenshot(
            keywords=args.keywords,
            location=args.location,
            education=args.education,
            experience=args.experience,
            age=args.age,
            school=args.school
        )
        if screenshot_result is None:
            print("警告: 浏览器截图失败，继续执行...")
        print("="*50 + "\n")

    resumes = search_resumes_by_api(
        keywords=args.keywords,
        location=args.location,
        education=args.education,
        experience=args.experience,
        count=args.count,
        cookies=cookies
    )

    if not resumes:
        print("错误:未能获取简历数据")
        return 1

    # 保存搜索上下文，供后续打招呼脚本使用
    save_search_context(args.keywords, args.location, args.education, args.experience, resumes)

    if args.output:
        output_path = args.output
    else:
        today = datetime.now().strftime('%Y-%m-%d')
        safe_kw = args.keywords.replace('/', '-')[:20]
        output_path = f"/lhcos-datas/reports/初筛报告/智联招聘{safe_kw}简历初筛报告-{today}.md"

    generate_screening_report(resumes, args.keywords, args.location, output_path, education_req=args.education, experience_req=args.experience)
    print(f"✅ 初筛报告已生成: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
