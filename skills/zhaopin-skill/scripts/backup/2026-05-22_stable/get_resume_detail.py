#!/usr/bin/env python3
"""
智联招聘详细简历获取脚本

正确流程：
1. 访问搜索页面
2. 输入岗位关键词进行搜索（触发搜索API: /api/talent/search/list）
3. 在搜索结果中找到目标候选人
4. 点击候选人卡片（触发详情API: /api/resume/detail）
5. 拦截详情API响应
6. 从详情API响应中提取完整简历数据
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Route


# 配置文件路径
COOKIE_FILE = "/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt"


def load_cookies(cookie_file=None):
    """加载Cookie"""
    if cookie_file is None:
        cookie_file = COOKIE_FILE
    
    if not os.path.exists(cookie_file):
        print(f"错误：Cookie配置文件不存在: {cookie_file}")
        return None
    
    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookies = f.read().strip()
    
    if not cookies:
        print(f"错误：Cookie文件为空: {cookie_file}")
        return None
    
    return cookies


def get_city_id(city_name):
    """将城市名转换为ID（与search_resumes.py一致）"""
    city_map = {
        "周口": 734, "郑州": 701, "北京": 530, "上海": 538,
        "深圳": 765, "广州": 703, "杭州": 653, "南京": 653,
    }
    return city_map.get(city_name, 734)


def build_filter_params(location=None, education=None, experience=None):
    """
    构建过滤参数（与search_resumes.py一致）
    返回用于API调用的过滤参数字典
    """
    params = {}
    
    # 城市
    if location:
        # 解析 location 格式: "河南-周口" 或 "周口"
        city_name = location.split('-')[-1] if '-' in location else location
        city_id = get_city_id(city_name)
        params['expectedCityIds'] = [city_id]
        print(f"   [过滤] 城市: {city_name} -> ID {city_id}")
    
    # 学历
    if education:
        edu_map = {"大专": "3", "本科": "4", "硕士": "10", "博士": "5"}
        edu_levels = [edu_map[e] for e in edu_map if e in education]
        if edu_levels:
            params['educations'] = edu_levels
            print(f"   [过滤] 学历: {education} -> {edu_levels}")
    
    # 经验
    if experience:
        exp_map = {"1年以下": "2", "1-3年": "3", "3-5年": "4", "5-10年": "5", "10年以上": "6"}
        exp_levels = [exp_map[e] for e in exp_map if e in experience]
        if exp_levels:
            params['workingYears'] = exp_levels
            print(f"   [过滤] 经验: {experience} -> {exp_levels}")
    
    return params


def get_resume_detail_by_name(candidate_name, job_keyword, cookies=None, location=None, education=None, experience=None, enable_screenshot=False):
    """
    根据候选人姓名和岗位关键词获取详细简历
    
    正确流程：
    1. 访问搜索页面
    2. 输入岗位关键词进行搜索（触发搜索API）
    3. 在搜索结果中找到目标候选人
    4. 点击候选人卡片（触发详情API）
    5. 拦截详情API响应
    6. 从详情API响应中提取完整简历数据
    """
    if cookies is None:
        cookies = load_cookies()
        if cookies is None:
            return None
    
    print(f"开始获取候选人 '{candidate_name}' 的详细简历...")
    print(f"岗位关键词: {job_keyword}")
    
    # 保存截图和数据的目录
    debug_dir = "/tmp/zhaopin_debug"
    os.makedirs(debug_dir, exist_ok=True)
    
    search_api_response = None  # 用于存储搜索API响应
    detail_api_response = None  # 用于存储详情API响应
    detail_api_buffer = []  # 用于缓冲所有详情API响应
    target_resume_data = None  # 用于存储目标候选人的数据（从搜索结果中找到）
    target_resume_index = None  # 用于存储目标候选人在搜索结果中的索引
    target_resume_number = None  # 用于存储目标候选人的resumeNumber
    click_time = None  # 用于存储点击卡片的时间戳
    search_api_received = False  # 标记是否已收到搜索API响应
    
    # 使用单个响应处理器，根据URL判断数据类型
    def handle_response(response):
        nonlocal search_api_response, detail_api_response, target_resume_data, target_resume_index, target_resume_number, click_time, search_api_received, detail_api_buffer
        url = response.url
        import time
        current_time = time.time()
        
        # 处理搜索API响应
        if '/api/talent/search/list' in url and response.status == 200:
            try:
                data = response.json()
                if data and data.get('code') == 200:
                    print(f"   ✅ 拦截到搜索API响应")
                    search_api_response = data
                    search_api_received = True
                    
                    # 在响应中查找目标候选人
                    results = data.get('data', {}).get('list', [])
                    print(f"   [调试] 搜索API返回 {len(results)} 条结果")
                    for idx, item in enumerate(results):
                        user_name = item.get('userName', '')
                        resume_number = item.get('resumeNumber', '')
                        if user_name == candidate_name:
                            print(f"   ✅ 在搜索结果中找到目标候选人: {user_name} (索引: {idx}, resumeNumber: {resume_number})")
                            target_resume_data = item
                            target_resume_index = idx
                            target_resume_number = resume_number
                            break
                    # 搜索API响应后，检查是否找到了目标候选人
                    # 如果JavaScript拦截器不工作（筛选条件未生效），尝试在页面上直接搜索
                    if not target_resume_data:
                        print(f"   ⚠️ JavaScript拦截器可能未生效，尝试在页面上查找候选人...")
                        # 在页面文本中查找候选人
                        body_text = page.inner_text('body')
                        if candidate_name in body_text:
                            print(f"   ✅ 候选人在页面中找到，尝试点击卡片...")
                            # 点击候选人卡片 - 通过姓名匹配
                            click_result = page.evaluate(f'''(name) => {{
                                var cards = document.querySelectorAll('.search-resume-item-wrap');
                                for (var j = 0; j < cards.length; j++) {{
                                    var c = cards[j];
                                    var text = c.textContent || '';
                                    if (text.indexOf(name) !== -1) {{
                                        c.scrollIntoViewIfNeeded();
                                        c.click();
                                        return {{ success: true, index: j }};
                                    }}
                                }}
                                return {{ success: false }};
                            }}''', candidate_name)
                            if click_result.get('success'):
                                target_resume_index = click_result.get('index')
                                print(f"   ✅ 点击卡片成功，索引: {{target_resume_index}}")
                                return None  # 继续等待详情API
                            else:
                                print(f"   ⚠️ 未找到候选人卡片")
                        else:
                            print(f"   ⚠️ 候选人 '{candidate_name}' 不在搜索结果中")
                    
                    # 搜索API响应后，检查缓冲区中是否有匹配的数据
                    if target_resume_number and not detail_api_response:
                        for buffered in detail_api_buffer:
                            buffered_resume_id = buffered.get('data', {}).get('resume', {}).get('id', '')
                            buffered_user_name = buffered.get('data', {}).get('user', {}).get('name', '')
                            
                            # 优先用resumeId匹配（但search API的resumeNumber和detail API的resume.id可能不同）
                            if buffered_resume_id and buffered_resume_id == target_resume_number:
                                print(f"   ✅ 从缓冲区找到resumeId匹配: {buffered_user_name}")
                                detail_api_response = buffered
                                break
                            # 如果resumeId不匹配，尝试精确name匹配
                            if buffered_user_name == candidate_name:
                                print(f"   ✅ 从缓冲区找到name匹配: {buffered_user_name} == {candidate_name}")
                                detail_api_response = buffered
                                break
            except Exception as e:
                print(f"   解析搜索响应失败: {e}")
        
        # 处理详情API响应 - 缓冲所有响应，之后再过滤
        if '/api/resume/detail' in url and response.status == 200:
            try:
                data = response.json()
                if data and data.get('code') == 200:
                    user_obj = data.get('data', {}).get('user', {})
                    resume_obj = data.get('data', {}).get('resume', {})
                    user_name = user_obj.get('name', '')
                    resume_id = resume_obj.get('id', '')
                    print(f"   📋 详情API响应: {user_name}")
                    
                    # 如果已经知道目标候选人，立即检查是否匹配
                    if target_resume_number and resume_id:
                        # resumeId匹配（但search API的resumeNumber和detail API的resume.id可能格式不同）
                        if resume_id == target_resume_number:
                            print(f"   ✅ resumeId匹配！这是目标候选人 {candidate_name} 的详情")
                            if detail_api_response is None:
                                detail_api_response = data
                        else:
                            # resumeId不匹配，尝试精确name匹配
                            if user_name == candidate_name:
                                print(f"   ✅ name匹配: {user_name} == {candidate_name}")
                                if detail_api_response is None:
                                    detail_api_response = data
                    else:
                        # 缓冲响应，等待搜索API来确定目标
                        if not detail_api_response:
                            detail_api_buffer.append(data)
                            print(f"   📦 缓冲详情API响应（当前缓冲: {len(detail_api_buffer)}条）")
            except Exception as e:
                print(f"   解析详情响应失败: {e}")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # 设置Cookie
            print("1. 设置Cookie...")
            for item in cookies.split(';'):
                item = item.strip()
                if '=' in item:
                    name, value = item.split('=', 1)
                    try:
                        context.add_cookies([{
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.rd6.zhaopin.com',
                            'path': '/'
                        }])
                    except:
                        pass
            
            # 访问搜索页面
            print("2. 访问搜索页面...")
            page.goto("https://rd6.zhaopin.com/app/search", timeout=30000)
            page.wait_for_timeout(2000)
            if enable_screenshot:
                page.screenshot(path=f"{debug_dir}/01_search_page.png")
            
            # 输入岗位关键词（不是候选人姓名！）
            print(f"3. 输入岗位关键词: {job_keyword}")
            page.evaluate(f'''
                () => {{
                    const inputs = document.querySelectorAll('input');
                    for (const input of inputs) {{
                        if (input.className && input.className.includes('keyword-input')) {{
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(input, '{job_keyword}');
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            console.log('Set job keyword successfully');
                            return;
                        }}
                    }}
                    const keywordInput = document.querySelector('.keyword-input-tag-item-input__input');
                    if (keywordInput) {{
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(keywordInput, '{job_keyword}');
                        keywordInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        keywordInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}
            ''')
            page.wait_for_timeout(500)
            
            # 设置过滤条件（与search_resumes.py一致）
            if location or education or experience:
                print(f"   [过滤] 地点={location}, 学历={education}, 经验={experience}")
                # 尝试展开筛选面板
                page.evaluate('''() => {
                    const btns = document.querySelectorAll('button, div[role="button"], div[class*="filter"]');
                    for (const btn of btns) {
                        const text = btn.textContent || '';
                        if (text.includes('筛选') || text.includes('城市') || text.includes('条件') || text.includes('选项')) {
                            btn.click();
                            break;
                        }
                    }
                }''')
                page.wait_for_timeout(1000)
            
            # 注册统一的响应处理器
            page.on('response', handle_response)
            
            # 使用Playwright的route方法拦截请求（比JavaScript拦截更可靠）
            if location or education or experience:
                filter_params = build_filter_params(location, education, experience)
                print(f"   [Route拦截] 设置过滤参数: {filter_params}")
                
                # 定义路由处理器
                def handle_route(route: Route):
                    """拦截搜索API请求并添加过滤参数"""
                    request = route.request
                    if '/api/talent/search/list' in request.url:
                        print(f"   [Route拦截] 拦截到搜索API请求: {request.url[:80]}")
                        # 获取原始请求数据
                        post_data = request.post_data
                        if post_data:
                            try:
                                import json
                                data = json.loads(post_data)
                                print(f"   [Route拦截] 原始body: {str(data)[:200]}")
                                # 添加过滤参数
                                for key, value in filter_params.items():
                                    if key not in data:
                                        data[key] = value
                                        print(f"   [Route拦截] 添加参数: {key} = {value}")
                                # 继续请求 with modified data
                                route.continue_(post_data=json.dumps(data))
                                print(f"   [Route拦截] 修改后body: {str(data)[:200]}")
                            except Exception as e:
                                print(f"   [Route拦截] 解析请求数据失败: {e}")
                                route.continue_()
                        else:
                            route.continue_()
                    else:
                        route.continue_()
                
                # 注册路由处理器
                page.route("**/api/talent/search/list", handle_route)
                print(f"   [Route拦截] 已注册路由拦截器")
            
            # 点击搜索按钮
            print("4. 点击搜索...")
            page.evaluate('''() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent.trim();
                    if (text === '搜 索' || text === '搜索') {
                        btn.click();
                        console.log('Clicked search button');
                        break;
                    }
                }
            }''')
            
            # 等待搜索结果加载
            print("5. 等待搜索结果...")
            page.wait_for_timeout(8000)
            if enable_screenshot:
                page.screenshot(path=f"{debug_dir}/02_search_results.png")
            
            # 获取页面文本
            body_text = page.inner_text('body')
            print(f"   页面文本长度: {len(body_text)} 字符")
            
            # 检查是否在搜索结果中找到了目标候选人
            if not target_resume_data:
                print(f"   ⚠️ 在搜索API响应中未找到候选人 '{candidate_name}'")
                if candidate_name in body_text:
                    print(f"   候选人在页面中，继续尝试点击...")
                else:
                    print(f"   ⚠️ 候选人 '{candidate_name}' 不在搜索结果中")
                    browser.close()
                    return None
            
            # 找到了候选人，现在需要点击卡片并拦截详情API
            print(f"6. 点击候选人卡片，触发详情API...")
            
            # 设置点击时间（在点击之前）
            import time
            click_time = time.time()
            print(f"   点击时间戳: {click_time}")
            
            # 点击候选人卡片 - 使用搜索结果索引或姓名匹配
            click_result = page.evaluate('''(args) => {
                var targetIdx = args[0];
                var name = args[1];
                var cards = document.querySelectorAll('.search-resume-item-wrap');
                
                // 调试：打印所有卡片的姓名
                var debugInfo = [];
                for (var k = 0; k < Math.min(cards.length, 5); k++) {
                    var c = cards[k];
                    var text = c.textContent || '';
                    // 提取姓名（包含"先生"或"女士"的行）
                    var lines = text.split('\\n');
                    var cardName = '';
                    for (var l = 0; l < lines.length; l++) {
                        var line = lines[l].trim();
                        if (line.indexOf('先生') !== -1 || line.indexOf('女士') !== -1) {
                            cardName = line.trim();
                            break;
                        }
                    }
                    debugInfo.push({index: k, name: cardName, preview: text.substring(0, 100)});
                }
                
                if (targetIdx !== null && targetIdx !== undefined && targetIdx < cards.length) {
                    var card = cards[targetIdx];
                    var lines = card.textContent.split('\\n');
                    var cardName = '';
                    for (var i = 0; i < lines.length; i++) {
                        var line = lines[i].trim();
                        if (line.indexOf('先生') !== -1 || line.indexOf('女士') !== -1) {
                            cardName = line;
                            break;
                        }
                    }
                    card.scrollIntoViewIfNeeded();
                    card.click();
                    return { success: true, index: targetIdx, method: 'index', cardName: cardName, debug: debugInfo };
                }
                for (var j = 0; j < cards.length; j++) {
                    var c = cards[j];
                    var text = c.textContent || '';
                    if (text.indexOf(name) !== -1 && text.indexOf(name) < 200) {
                        c.scrollIntoViewIfNeeded();
                        c.click();
                        var lines = c.textContent.split('\\n');
                        var cardName = '';
                        for (var i = 0; i < lines.length; i++) {
                            var line = lines[i].trim();
                            if (line.indexOf('先生') !== -1 || line.indexOf('女士') !== -1) {
                                cardName = line;
                                break;
                            }
                        }
                        return { success: true, index: j, method: 'name', cardName: cardName, debug: debugInfo };
                    }
                }
                return { success: false, debug: debugInfo };
            }''', arg=(target_resume_index, candidate_name))
            
            if click_result.get('success'):
                method = click_result.get('method', 'unknown')
                card_name = click_result.get('cardName', 'N/A')
                debug_info = click_result.get('debug', [])
                print(f"   点击卡片成功: index={click_result.get('index')}, method={method}, cardName={card_name}")
                print(f"   调试信息 - 前5张卡片:")
                for info in debug_info:
                    print(f"     [{info.get('index')}] {info.get('name')} - {info.get('preview')[:50]}...")
            else:
                print(f"   ⚠️ 点击卡片失败")
                print(f"   调试信息: {click_result.get('debug', [])}")
                browser.close()
                return None
            
            # 等待详情API响应（增加等待时间，因为API可能需要更长时间）
            print("7. 等待详情API响应...")
            page.wait_for_timeout(3000)  # 等待3秒让弹窗开始出现
            
            # 尝试等待弹窗元素出现
            try:
                # 等待常见的弹窗选择器
                popup_selectors = [
                    '.resume-detail-popup',
                    '.candidate-detail-popup',
                    '[role="dialog"]',
                    '.modal',
                    '.popup',
                    '.detail-modal',
                    '.sdetail',
                    '.resume-detail-wrap'
                ]
                
                for selector in popup_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=3000)
                        print(f"   ✅ 找到弹窗元素: {selector}")
                        break
                    except:
                        continue
                
                # 额外等待2秒让弹窗完全渲染
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"   等待弹窗时出错: {e}")
            
            # 截图弹窗页面
            if enable_screenshot:
                page.screenshot(path=f"{debug_dir}/03_after_click.png")
                print(f"   ✅ 已保存弹窗截图")
            
            # 检查详情API响应
            if detail_api_response:
                # 验证返回的候选人姓名是否匹配
                response_data = detail_api_response.get('data', {})
                user_info = response_data.get('user', {})
                resume_info = response_data.get('resume', {})
                returned_name = user_info.get('name', '')
                returned_resume_number = resume_info.get('resumeNumber', '')
                
                # 获取搜索时目标候选人的resumeNumber
                target_resume_number = target_resume_data.get('resumeNumber', '') if target_resume_data else ''
                
                print(f"   验证信息：")
                print(f"   - 预期候选人: {candidate_name} (resumeNumber: {target_resume_number})")
                print(f"   - 详情API返回: {returned_name} (resumeNumber: {returned_resume_number})")
                
                # 首先用resumeNumber精确验证（如果双方都有）
                if target_resume_number and returned_resume_number:
                    if target_resume_number == returned_resume_number:
                        print(f"   ✅ resumeNumber匹配一致，获取详情成功")
                        browser.close()
                        return extract_resume_from_detail_api(detail_api_response, candidate_name, target_resume_data)
                    else:
                        print(f"   ❌ resumeNumber不匹配！预期: {target_resume_number}, 实际: {returned_resume_number}")
                        print(f"   ⚠️ 点击了错误的卡片，使用搜索API数据作为后备")
                        if target_resume_data:
                            return extract_resume_from_search_item(target_resume_data, candidate_name)
                        else:
                            print(f"   ⚠️ 无法获取候选人数据")
                            browser.close()
                            return None
                
                # 如果没有resumeNumber，用姓名验证（允许模糊匹配）
                is_match = (
                    returned_name == candidate_name or
                    candidate_name.replace('先生', '').replace('女士', '') in returned_name or
                    returned_name.replace('先生', '').replace('女士', '') in candidate_name
                )
                
                if is_match:
                    print(f"   ✅ 姓名验证通过：{returned_name} == {candidate_name}")
                    browser.close()
                    return extract_resume_from_detail_api(detail_api_response, candidate_name, target_resume_data)
                else:
                    print(f"   ⚠️ 候选人姓名不匹配！预期: {candidate_name}, 实际: {returned_name}")
                    print(f"   ⚠️ 可能是点击了错误的卡片，使用搜索API数据作为后备")
                    if target_resume_data:
                        return extract_resume_from_search_item(target_resume_data, candidate_name)
                    else:
                        print(f"   ⚠️ 无法获取候选人数据")
                        browser.close()
                        return None
            else:
                # 调试：打印所有捕获到的API响应
                print(f"   ⚠️ 未能获取详情API响应，检查是否有其他响应...")
                # 如果详情API没有获取到，使用搜索API的数据作为后备
                if target_resume_data:
                    print(f"   使用搜索API数据作为后备")
                    return extract_resume_from_search_item(target_resume_data, candidate_name)
                else:
                    print(f"   ⚠️ 无法获取候选人数据")
                    browser.close()
                    return None
            
        except Exception as e:
            print(f"获取简历详情失败: {e}")
            import traceback
            traceback.print_exc()
            browser.close()
            return None


def extract_resume_from_detail_api(detail_data, candidate_name, search_data=None):
    """
    从详情API响应中提取完整简历数据
    
    详情API返回的数据结构：
    {
        "code": 200,
        "data": {
            "user": {           // 用户基本信息
                "name": "葛先生",
                "ageLabel": "33岁",
                "genderLabel": "男",
                "workYearsLabel": "9年",
                "maxEducationLabel": "本科",
                "careerStateLabel": "在职-正在找工作",
                "cityLabel": "现居北京 昌平区"
            },
            "resume": {          // 详细简历信息
                "workExperiences": [...],  // 工作经历
                "educationExperiences": [...],  // 教育经历
                "projectExperiences": [...],  // 项目经历
                "skillTags": [...],     // 技能标签
                "selfEvaluation": "..."  // 自我评价
            }
        }
    }
    """
    try:
        print("   正在从详情API响应中解析简历数据...")
        
        data = detail_data.get('data', {})
        user_info = data.get('user', {})
        resume_info = data.get('resume', {})
        
        # 基本信息
        name = user_info.get('name', candidate_name)
        gender = user_info.get('genderLabel', '')
        age = user_info.get('ageLabel', '')
        work_years = user_info.get('workYearsLabel', '')
        education = user_info.get('maxEducationLabel', '')
        career_status = user_info.get('careerStateLabel', '')
        city = user_info.get('cityLabel', '')
        
        # 工作经历
        work_exps = resume_info.get('workExperiences', [])
        work_exp_list = []
        work_exp_raw = []  # 保存原始数据供后续处理
        for exp in work_exps:
            company = exp.get('orgName', '') or exp.get('simpleOrgName', '')
            position = exp.get('jobTitle', '')
            time_label = exp.get('timeLabel', '')  # 详情API使用timeLabel，不是duration
            description = exp.get('description', '')
            
            # 构建工作经历字符串：公司 | 职位 | 时间
            exp_str = f"{company} | {position} | {time_label}"
            if description:
                exp_str += f"\n\n{description}"  # 完整工作内容，不截断
            work_exp_list.append(exp_str)
            work_exp_raw.append(exp)  # 保存原始数据
        
        # 教育经历
        edu_exps = resume_info.get('educationExperiences', [])
        edu_list = []
        for exp in edu_exps:
            school = exp.get('schoolName', '')
            major = exp.get('majorName', '')
            edu = exp.get('educationLevel', '')
            time_label = exp.get('educationTimeLabel', '')
            edu_str = f"{time_label} {school} {major} {edu}"
            edu_list.append(edu_str)
        
        # 项目经历
        proj_exps = resume_info.get('projectExperiences', [])
        proj_list = []
        for exp in proj_exps:
            proj_name = exp.get('name', '')
            time_label = exp.get('timeLabel', '')
            description = exp.get('description', '')
            resp = exp.get('responsibility', '')
            proj_str = f"### {proj_name}\n{time_label}\n{description}"
            if resp:
                proj_str += f"\n职责：{resp}"
            proj_list.append(proj_str)
        
        # 技能标签
        skill_tags = resume_info.get('skillTags', [])
        if isinstance(skill_tags, list):
            # skill_tags可能是字符串列表或字典列表，需要处理两种情况
            skills_list = [tag if isinstance(tag, str) else tag.get('name', '') for tag in skill_tags]
            skills_str = ', '.join([s for s in skills_list if s])
        else:
            skills_str = str(skill_tags)
            skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
        
        # 自我评价
        self_evaluation = resume_info.get('selfEvaluation', '')
        if isinstance(self_evaluation, list):
            self_evaluation = '\n'.join(self_evaluation)
        
        # 活跃状态：从careerStateLabel推断或设置为"智联招聘未提供"
        # careerStateLabel格式如"在职-正在找工作"、"在校-正在找工作"
        active_status = ''
        if career_status:
            if '在职' in career_status:
                active_status = '在职（看机会）'
            elif '离职' in career_status:
                active_status = '离职'
            elif '在校' in career_status or '应届' in career_status:
                active_status = '学生'
            else:
                active_status = career_status
        else:
            # 从最新工作经历的时间判断是否在职
            if work_exps:
                latest_exp = work_exps[0] if work_exps else {}
                end_date = latest_exp.get('endDate', '')
                if not end_date or '至今' in str(end_date):
                    active_status = '在职'
                else:
                    active_status = '离职'
        
        # 推荐理由：根据简历内容生成
        recommended_reason = generate_recommendation_reason(name, education, work_years, skills_list, work_exps)
        
        # 构建结果
        result = {
            '姓名': name,
            '性别': gender,
            '年龄': age,
            '学历': education,
            '工作年限': work_years,
            '当前职业状态': career_status,
            '所在城市': city,
            '活跃状态': active_status,
            '在线状态': '',
            '工作经历': work_exp_list,
            '工作经历原始': work_exps,
            '工作经历字符串': ' '.join([exp.get('orgName', '') + ' ' + exp.get('jobTitle', '') for exp in work_exps]),
            '教育经历': edu_list,
            '项目经历': proj_list,
            '技能标签': skills_str,
            '技能列表': skills_list,
            '证书': [],
            '自我评价': self_evaluation,
            '推荐理由': recommended_reason,
            '简历来源': '详情API'
        }
        
        # 从搜索API数据中提取期望薪资和期望职位（detail API没有这些字段）
        if search_data:
            if not result.get('期望薪资'):
                result['期望薪资'] = search_data.get('desiredSalary', '')
            if not result.get('期望职位'):
                result['期望职位'] = search_data.get('desiredJobType', '')
        else:
            result['期望薪资'] = result.get('期望薪资', '')
            result['期望职位'] = ''
        
        print(f"   解析完成: 姓名={name}, 工作经历={len(work_exp_list)}条, 教育经历={len(edu_list)}条, 项目经历={len(proj_list)}条")
        return result
        
    except Exception as e:
        print(f"   从详情API解析简历数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_resume_from_search_item(item, candidate_name):
    """从搜索结果项中提取简历数据（作为后备方案）"""
    try:
        print("   正在从搜索API响应中解析简历数据...")
        
        # 提取基本信息
        user_name = item.get('userName', candidate_name)
        gender = '男' if item.get('genderKey') == '1' else '女'
        if not gender:
            gender = item.get('gender', '男' if '先生' in candidate_name else '女')
        
        age = f"{item.get('age', '')}岁" if item.get('age') else ''
        work_years = item.get('workYearsLabel', '')
        
        # 学历
        education = item.get('educationLevel', '')
        
        career_status = item.get('careerStatus', '')
        desired_salary = item.get('desiredSalary', '')
        desired_city = item.get('desiredCity', '')
        active_tag = ''
        if isinstance(item.get('newUserActiveTag'), dict):
            active_tag = item.get('newUserActiveTag', {}).get('describe', '')
        online = '在线' if item.get('online') else '离线'
        
        # 提取工作经历
        work_exps = item.get('workExperiences', [])
        work_exp_list = []
        for exp in work_exps:
            company = exp.get('companyName', '')
            position = exp.get('jobTitle', '')
            duration = exp.get('duration', '')
            description = exp.get('description', '')
            exp_str = f"{duration} {company} {position}"
            if description:
                exp_str += f"\n    {description[:300]}..." if len(description) > 300 else f"\n    {description}"
            work_exp_list.append(exp_str)
        
        # 提取教育经历
        edu_exps = item.get('educationExperiences', [])
        edu_list = []
        for exp in edu_exps:
            school = exp.get('schoolName', '')
            major = exp.get('majorName', '')
            edu = exp.get('educationLevel', '')
            time_label = exp.get('educationTimeLabel', '')
            edu_str = f"{time_label} {school} {major} {edu}"
            edu_list.append(edu_str)
            if not education and edu:
                education = edu
        
        # 提取项目经历
        proj_exps = item.get('projectExperiences', [])
        proj_list = []
        for exp in proj_exps[:3]:
            proj_name = exp.get('name', '')
            time_label = exp.get('timeLabel', '')
            description = exp.get('description', '')
            proj_str = f"### {proj_name}\n{time_label}\n{description}"
            proj_list.append(proj_str)
        
        # 从highlightResult提取项目数据
        highlight_result = item.get('highlightResult', {})
        hr_project_name = highlight_result.get('projectName', '') if isinstance(highlight_result, dict) else ''
        hr_project_desc = highlight_result.get('projectDescription', '') if isinstance(highlight_result, dict) else ''
        hr_project_resp = highlight_result.get('projectResponsibility', '') if isinstance(highlight_result, dict) else ''
        
        if hr_project_name and hr_project_name.strip():
            hr_proj_str = f"### {hr_project_name.strip()}\n"
            if hr_project_desc:
                hr_proj_str += f"{hr_project_desc.strip()}\n"
            if hr_project_resp:
                hr_proj_str += f"职责：{hr_project_resp.strip()}"
            proj_list.append(hr_proj_str)
        
        # 提取技能标签
        display_tags = item.get('displayTags', [])
        skills = [tag.get('name', '') for tag in display_tags if tag.get('name')]
        skills_str = ', '.join(skills) if skills else ''
        
        # 证书
        certificates = item.get('certificateNames', [])
        
        # 推荐理由
        recommended_reason = item.get('recommendedReason', '')
        
        # 自我评价
        self_evaluation = item.get('selfEvaluation', '')
        if isinstance(self_evaluation, list):
            self_evaluation = '\n'.join(self_evaluation)
        
        # 构建结果
        result = {
            '姓名': user_name,
            '性别': gender,
            '年龄': age,
            '学历': education,
            '工作年限': work_years,
            '当前职业状态': career_status,
            '期望薪资': desired_salary,
            '所在城市': desired_city,
            '期望职位': item.get('desiredJobType', ''),
            '活跃状态': active_tag,
            '在线状态': online,
            '工作经历': work_exp_list,
            '工作经历原始': work_exps,
            '工作经历字符串': ' '.join([exp.get('companyName', '') + ' ' + exp.get('jobTitle', '') for exp in work_exps]),
            '教育经历': edu_list,
            '项目经历': proj_list,
            '项目经历_高亮': {'name': hr_project_name, 'description': hr_project_desc, 'responsibility': hr_project_resp},
            '技能标签': skills_str,
            '技能列表': skills,
            '证书': certificates if isinstance(certificates, list) else [],
            '自我评价': self_evaluation,
            '推荐理由': recommended_reason,
            '简历来源': '搜索API'
        }
        
        print(f"   解析完成: 姓名={user_name}, 工作经历={len(work_exp_list)}条, 教育经历={len(edu_list)}条")
        return result
        
    except Exception as e:
        print(f"解析简历数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def summarize_work_experience(work_exps, resume_data):
    """总结工作经历 - 将每段工作经历总结为2-4句的连贯段落，不是简单罗列"""
    # 优先使用已格式化的完整工作经历（包含描述）
    formatted_work_exps = resume_data.get('工作经历', [])
    raw_work_exps = resume_data.get('工作经历原始', [])
    
    if not raw_work_exps:
        raw_work_exps = work_exps if isinstance(work_exps, list) else []
    
    if not raw_work_exps or len(raw_work_exps) == 0:
        return "暂无工作经历"
    
    exp_summaries = []
    
    for exp in raw_work_exps:
        if isinstance(exp, str):
            exp_summaries.append(exp)
            continue
        
        company = exp.get('orgName', '') or exp.get('simpleOrgName', '') or exp.get('companyName', '')
        position = exp.get('jobTitle', '')
        
        # 优先使用timeLabel（详情API），其次使用beginDate/endDate（搜索API）
        time_label = exp.get('timeLabel', '')
        if not time_label:
            begin_date = exp.get('beginDate', '')
            end_date = exp.get('endDate', '')
            duration = exp.get('duration', '')
            if begin_date and end_date:
                time_range = f"{begin_date} 至 {end_date}"
            elif begin_date:
                time_range = f"{begin_date} 至今"
            else:
                time_range = duration if duration else '时间不详'
            time_label = time_range
        
        # 获取工作描述，生成总结
        description = exp.get('description', '')
        
        if description:
            # 对描述进行智能摘要：提取关键信息，生成2-4句连贯段落
            lines = [l.strip() for l in description.split('\n') if l.strip()]
            sentences = []
            for line in lines:
                # 清理每行，去除序号（如"1."、"2."等）
                cleaned = re.sub(r'^\d+[.)]\s*', '', line).strip()
                if cleaned:
                    sentences.append(cleaned)
            
            # 对描述进行智能摘要：提取关键信息，生成2-3句连贯段落
            if sentences:
                # 取前3个要点，用连贯的方式表达
                key_points = sentences[:3]
                # 清理每个要点的末尾标点
                cleaned_points = []
                for point in key_points:
                    # 去除末尾的句号、顿号等，以及开头的序号
                    point = re.sub(r'^\d+[.)]?\s*', '', point)  # 去除开头的序号如"1."或"1"
                    point = point.rstrip('。．.')
                    cleaned_points.append(point)
                
                if len(cleaned_points) >= 3:
                    # 生成连贯段落
                    summary = f"主要负责{cleaned_points[0]}，并参与{cleaned_points[1]}；此外还负责{cleaned_points[2]}"
                elif len(cleaned_points) == 2:
                    summary = f"主要负责{cleaned_points[0]}，同时参与{cleaned_points[1]}"
                elif len(cleaned_points) == 1:
                    summary = f"主要负责{cleaned_points[0]}"
                else:
                    summary = description[:150] + '...' if len(description) > 150 else description
        else:
            summary = f"负责{position}相关工作"
        
        # 构建完整的工作经历总结：公司 | 职位 | 时间
        if company and position:
            exp_summary = f"**{company} | {position} | {time_label}**\n{summary}"
            exp_summaries.append(exp_summary)
        elif company:
            exp_summaries.append(f"**{company} | {time_label}**\n{summary}")
    
    if not exp_summaries:
        return "工作经历详情见基本信息"
    
    # 各工作经历之间用双换行分隔
    return '\n\n'.join(exp_summaries)


def summarize_project_experience(proj_exps, resume_data=None):
    """总结项目经历 - 包含项目名称、时间和主要项目内容"""
    if not proj_exps or (isinstance(proj_exps, list) and len(proj_exps) == 0):
        if resume_data:
            hr_proj = resume_data.get('项目经历_高亮', {})
            hr_name = hr_proj.get('name', '')
            hr_desc = hr_proj.get('description', '')
            hr_resp = hr_proj.get('responsibility', '')
            if hr_name and hr_name.strip():
                summary_parts = [f"**{hr_name.strip()}**"]
                if hr_desc and hr_desc.strip():
                    summary_parts.append(hr_desc.strip())
                if hr_resp and hr_resp.strip():
                    summary_parts.append(f"职责：{hr_resp.strip()}")
                return '\n'.join(summary_parts) if summary_parts else "暂无项目经历"
        return "暂无项目经历"
    
    proj_summaries = []
    for exp in proj_exps:
        if isinstance(exp, str):
            lines = exp.split('\n')
            if lines:
                proj_name = lines[0].replace('### ', '').strip()
                if proj_name:
                    summary_parts = [f"**{proj_name}**"]
                    # 如果有第二行（时间），添加时间信息
                    if len(lines) > 1 and lines[1].strip():
                        summary_parts.append(lines[1].strip())
                    # 如果有第三行及以后（项目描述），添加描述
                    if len(lines) > 2:
                        desc_lines = [l.strip() for l in lines[2:] if l.strip()]
                        if desc_lines:
                            # 对描述进行整理，生成连贯的项目描述
                            cleaned = []
                            for d in desc_lines[:3]:
                                cleaned_d = re.sub(r'^\d+[.)]?\s*', '', d).strip()  # 去除开头的序号如"1."或"1"
                                cleaned_d = cleaned_d.rstrip('。．.')
                                if cleaned_d:
                                    cleaned.append(cleaned_d)
                            if cleaned:
                                if len(cleaned) >= 2:
                                    proj_desc = f"主要工作包括：{cleaned[0]}，并通过{cleaned[1]}"
                                    if len(cleaned) > 2:
                                        proj_desc += f"，此外还负责{cleaned[2]}"
                                else:
                                    proj_desc = f"主要工作：{cleaned[0]}"
                                summary_parts.append(proj_desc)
                    proj_summaries.append('\n'.join(summary_parts))
        else:
            # 处理字典格式的项目数据
            proj_name = exp.get('name', '')
            time_label = exp.get('timeLabel', '')
            description = exp.get('description', '')
            resp = exp.get('responsibility', '')
            
            if proj_name:
                summary_parts = [f"**{proj_name}**"]
                if time_label:
                    summary_parts.append(time_label)
                if description:
                    # 清理并截取描述，生成连贯的项目描述
                    desc_lines = [l.strip() for l in description.split('\n') if l.strip()]
                    cleaned = []
                    for d in desc_lines[:3]:
                        cleaned_d = re.sub(r'^\d+[.)]?\s*', '', d).strip()  # 去除开头的序号如"1."或"1"
                        cleaned_d = cleaned_d.rstrip('。．.')
                        if cleaned_d:
                            cleaned.append(cleaned_d)
                    if cleaned:
                        if len(cleaned) >= 2:
                            proj_desc = f"主要工作包括：{cleaned[0]}，并负责{cleaned[1]}"
                            if len(cleaned) > 2:
                                proj_desc += f"，同时参与{cleaned[2]}"
                        else:
                            proj_desc = f"主要工作：{cleaned[0]}"
                        summary_parts.append(proj_desc)
                if resp:
                    summary_parts.append(f"职责：{resp.strip()}")
                proj_summaries.append('\n'.join(summary_parts))
    
    if not proj_summaries:
        return "暂无项目经历"
    
    # 各项目之间用双换行分隔
    return '\n\n'.join(proj_summaries[:3])


def generate_detail_report(resume_data, job_title, output_path):
    """生成详细简历分析报告"""
    if not resume_data:
        print("没有简历数据，无法生成报告")
        return False
    
    today = datetime.now().strftime('%Y-%m-%d')
    name = resume_data.get('姓名', '未知')
    location = resume_data.get('所在城市', '未知')
    
    # 计算匹配度
    match_score = calculate_match_score(resume_data, job_title)
    match_stars = generate_match_stars(match_score)
    match_level = '优秀匹配' if match_score >= 8 else '良好匹配' if match_score >= 6 else '部分匹配' if match_score >= 4 else '匹配度低'
    
    # 处理工作经历
    work_exps = resume_data.get('工作经历', [])
    work_exp_summary = summarize_work_experience(work_exps, resume_data)
    
    # 处理教育经历
    edu_exps = resume_data.get('教育经历', [])
    if isinstance(edu_exps, list) and edu_exps:
        edu_str = '\n'.join([f"- {exp}" for exp in edu_exps])
    else:
        edu_str = '暂无'
    
    # 处理项目经历
    proj_exps = resume_data.get('项目经历', [])
    proj_summary = summarize_project_experience(proj_exps, resume_data)
    
    # 处理技能标签
    skills_list = resume_data.get('技能列表', [])
    if not skills_list:
        skills_str = resume_data.get('技能标签', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
    else:
        skills_str = ', '.join(skills_list)
    
    core_tags = '#' + ' #'.join(skills_list[:5]) if skills_list else '暂无'
    
    career_path = generate_career_path(resume_data)
    strengths = generate_strengths(resume_data, job_title)
    risks = generate_risks(resume_data, job_title)
    match_analysis = generate_match_analysis(resume_data, job_title, skills_list)
    interview_suggestions = generate_interview_suggestions(resume_data, job_title, skills_list, match_score)
    
    certs = resume_data.get('证书', [])
    if isinstance(certs, list) and certs:
        cert_str = '\n'.join([f"- {cert}" for cert in certs])
    else:
        cert_str = '暂无'
    
    self_eval = resume_data.get('自我评价', '')
    
    basic_info = f"""|项目|内容|
|-|-|
|姓名|{name}|
|性别|{resume_data.get('性别', '未知')}|
|年龄|{resume_data.get('年龄', '未知')}|
|学历|{resume_data.get('学历', '未知')}|
|工作年限|{resume_data.get('工作年限', '未知')}|
|期望薪资|{resume_data.get('期望薪资', '未知')}|
|所在城市|{location}|
|当前状态|{resume_data.get('当前职业状态', '未知')}|
|活跃状态|{resume_data.get('活跃状态', '未知')}|
|推荐理由|{resume_data.get('推荐理由', '暂无')}|
|简历来源|{resume_data.get('简历来源', '未知')}|
"""
    
    report = f"""# 简历分析报告：{name}

**分析日期**：{today}  
**应聘岗位**：{resume_data.get('期望职位') or job_title}  
**工作地点**：{location}
**整体匹配度**：{match_score}/10  {match_stars} {match_level}

---

## 🎯 人物画像

### 核心标签
{core_tags}

### 职业发展路径
{career_path}

### 个人优势
{strengths}

### 风险提示
{risks}

---

## 🔍 岗位匹配度评估

### 多维度匹配分析
{match_analysis.get('table', '暂无数据')}

### 匹配亮点
{match_analysis.get('highlights', '暂无')}

### 存在差距
{match_analysis.get('gaps', '暂无')}

---

## 💡 面试建议

### 🎯 面试结论
{interview_suggestions.get('conclusion', '暂无')}

### 重点考察方向
{interview_suggestions.get('focus', '暂无')}

### 参考提问问题
{interview_suggestions.get('questions', '暂无')}

### 背景调查关注点
{interview_suggestions.get('background', '暂无')}

### 薪资谈判建议
{interview_suggestions.get('salary', '暂无')}

---

## 📋 基本信息

{basic_info}
---

## 💼 工作经历

{work_exp_summary}

---

## 🚀 项目经历

{proj_summary}

---

## 🎓 教育背景

{edu_str}

---

## 🛠️ 技能证书

{skills_str if skills_str else '暂无'}
{cert_str if cert_str and cert_str != '暂无' else ''}

---

## 📝 自我评价

{self_eval if self_eval else '暂无'}

---

*本报告由AI自动生成，仅供内部招聘使用。*
"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 详细分析报告已生成: {output_path}")
    return True


def calculate_match_score(resume_data, job_title):
    """计算简历与岗位的匹配度"""
    score = 5.0
    
    skills_list = resume_data.get('技能列表', [])
    if not skills_list:
        skills_str = resume_data.get('技能标签', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
    
    job_keywords = ['大数据', '平台', '开发', 'Hadoop', 'Spark', 'Flink', '数据仓库', 'ETL', 'Python', 'Java', 'SQL', '区块链']
    skill_matches = sum(1 for kw in job_keywords if any(kw.lower() in skill.lower() for skill in skills_list))
    score += skill_matches * 0.5
    
    work_exp = resume_data.get('工作经历', [])
    if isinstance(work_exp, list) and work_exp:
        work_exp_str = ' '.join(work_exp)
    else:
        work_exp_str = ''
    
    relevant_exp_keywords = ['大数据', '数据开发', '数据仓库', 'Hadoop', 'Spark', '平台开发', '开发工程师', '算法', '联合利华', '科大讯飞']
    exp_matches = sum(1 for kw in relevant_exp_keywords if kw in work_exp_str)
    score += min(exp_matches * 0.5, 2.0)
    
    edu = resume_data.get('学历', '')
    if edu in ['本科', '硕士', '博士']:
        score += 0.5
    
    score = min(score, 10.0)
    score = max(score, 1.0)
    
    return score


def generate_match_stars(score):
    """将分数转换为星星"""
    full_stars = int(score // 2)
    half_star = 1 if score % 2 >= 1 else 0
    empty_stars = 5 - full_stars - half_star
    return '⭐' * full_stars + ('⭐' if half_star else '') + '☆' * empty_stars


def generate_career_path(resume_data):
    """生成职业发展路径描述"""
    work_exps = resume_data.get('工作经历', [])
    if not work_exps:
        return '暂无详细职业路径信息'
    
    work_years = resume_data.get('工作年限', '')
    edu = resume_data.get('学历', '')
    
    if '应届' in work_years or '在校' in resume_data.get('当前职业状态', ''):
        return f"{edu}应届毕业生，{len(work_exps)}段实习/工作经历，具备基础专业技能"
    
    num_exp = len(work_exps) if isinstance(work_exps, list) else 1
    return f"约{work_years}工作经验，具有{num_exp}段工作经历"


def generate_strengths(resume_data, job_title):
    """生成个人优势分析"""
    strengths = []
    
    skills_list = resume_data.get('技能列表', [])
    if not skills_list:
        skills_str = resume_data.get('技能标签', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
    
    work_years = resume_data.get('工作年限', '')
    edu = resume_data.get('学历', '')
    certs = resume_data.get('证书', [])
    
    if skills_list:
        if len(skills_list) >= 5:
            strengths.append(f"✅ 技能全面：掌握{', '.join(skills_list[:5])}等技能")
        else:
            strengths.append(f"✅ 具备技能：{', '.join(skills_list)}")
    
    if '应届' not in work_years and '在校' not in resume_data.get('当前职业状态', ''):
        strengths.append(f"✅ 有{work_years}工作经验，实际工作能力有保障")
    
    if edu in ['本科', '硕士', '博士']:
        strengths.append(f"✅ {edu}学历，理论基础扎实")
    
    if certs and isinstance(certs, list) and len(certs) > 0:
        strengths.append(f"✅ 持有{len(certs)}项证书/奖项，专业能力有背书")
    
    if '在职' in resume_data.get('当前职业状态', ''):
        strengths.append(f"✅ 目前在职，工作稳定性有保障")
    
    return '\n'.join(strengths) if strengths else '暂无明显优势'


def generate_risks(resume_data, job_title):
    """生成风险提示"""
    risks = []
    
    work_years = resume_data.get('工作年限', '')
    status = resume_data.get('当前职业状态', '')
    skills_list = resume_data.get('技能列表', [])
    
    if '应届' in work_years or '在校' in status:
        risks.append("⚠️ 应届生/在校生，缺乏正式工作经验，需要培养周期")
    
    if '离职' in status:
        risks.append("⚠️ 目前离职状态，需了解离职原因")
    
    job_keywords = ['大数据', 'Hadoop', 'Spark', '平台开发']
    has_relevant = any(any(kw.lower() in skill.lower() for kw in job_keywords) for skill in skills_list)
    if not has_relevant and skills_list:
        risks.append("⚠️ 技能标签与岗位要求匹配度待确认")
    
    salary = resume_data.get('期望薪资', '')
    if salary and ('1万' in salary or '2万' in salary or '3万' in salary):
        risks.append("⚠️ 薪资期望较高，需确认是否符合预算")
    
    return '\n'.join(risks) if risks else '暂无明显风险'


def generate_match_analysis(resume_data, job_title, skills_list):
    """生成岗位匹配度多维度分析"""
    if not skills_list:
        skills_str = resume_data.get('技能标签', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
    
    job_keywords = ['大数据', '平台', '开发', 'Hadoop', 'Spark', 'Flink', '数据仓库', 'ETL', 'Python', 'Java', 'SQL']
    skill_match = any(any(kw.lower() in skill.lower() for kw in job_keywords) for skill in skills_list)
    
    work_years = resume_data.get('工作年限', '')
    edu = resume_data.get('学历', '')
    location = resume_data.get('所在城市', '')
    
    skill_match_result = '✅ 符合' if skill_match else '⚠️ 部分匹配'
    skill_match_desc = f"匹配：{', '.join(skills_list[:3])}" if skill_match else f"部分匹配：{', '.join(skills_list[:3]) if skills_list else '暂无明确技能标签'}"
    
    exp_match_result = '✅ 符合' if '应届' not in work_years else '⚠️ 经验不足'
    
    edu_match_result = '✅ 符合' if edu in ['本科', '硕士', '博士'] else '⚠️ 学历偏低'
    
    location_match_result = '✅ 符合'
    
    table = f"""|匹配维度|匹配情况|详细说明|
|-|-|-|
|技能匹配|{skill_match_result}|{skill_match_desc}|
|经验匹配|{exp_match_result}|工作年限：{work_years or '未知'}|
|学历匹配|{edu_match_result}|{edu or '未知'}|
|地点匹配|{location_match_result}|期望地点：{location or '未知'}|
"""
    
    highlights_list = [
        f"技能{'匹配' if skill_match else '部分匹配'}：{', '.join(skills_list[:3])}" if skills_list else '暂无明确技能亮点',
        f"工作年限{work_years or '未知'}",
        f"{edu or '未知'}学历"
    ]
    highlights = "🌟 " + '\n🌟 '.join([h for h in highlights_list if h])
    
    gaps_list = [
        '技能与岗位要求匹配度需进一步确认' if not skill_match else '暂无明显差距',
        '缺乏正式工作经验' if '应届' in work_years else '暂无'
    ]
    gaps = "📉 " + '\n📉 '.join([g for g in gaps_list if g])
    
    return {'table': table, 'highlights': highlights, 'gaps': gaps}


def generate_recommendation_reason(name, education, work_years, skills_list, work_exps):
    """根据简历内容生成推荐理由"""
    reason_parts = []
    
    # 学历
    if education:
        reason_parts.append(f"{education}学历")
    
    # 工作年限
    if work_years:
        if '应届' in work_years or '在校' in work_years:
            reason_parts.append("应届/在校生")
        else:
            reason_parts.append(f"{work_years}工作经验")
    
    # 技能标签（取前3个）
    if skills_list and len(skills_list) > 0:
        top_skills = skills_list[:3]
        reason_parts.append(f"掌握{', '.join(top_skills)}等技能")
    
    # 工作经历中的公司
    if work_exps:
        companies = []
        for exp in work_exps[:2]:
            if isinstance(exp, dict):
                company = exp.get('orgName', '') or exp.get('simpleOrgName', '') or exp.get('companyName', '')
                if company and company not in companies:
                    companies.append(company)
        if companies:
            reason_parts.append(f"曾任职于{', '.join(companies)}")
    
    if reason_parts:
        return '，'.join(reason_parts)
    else:
        return '暂无推荐理由'
    """生成岗位匹配度多维度分析"""
    if not skills_list:
        skills_str = resume_data.get('技能标签', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
    
    job_keywords = ['大数据', '平台', '开发', 'Hadoop', 'Spark', 'Flink', '数据仓库', 'ETL', 'Python', 'Java', 'SQL']
    skill_match = any(any(kw.lower() in skill.lower() for kw in job_keywords) for skill in skills_list)
    
    work_years = resume_data.get('工作年限', '')
    edu = resume_data.get('学历', '')
    location = resume_data.get('所在城市', '')
    
    skill_match_result = '✅ 符合' if skill_match else '⚠️ 部分匹配'
    skill_match_desc = f"匹配：{', '.join(skills_list[:3])}" if skill_match else f"部分匹配：{', '.join(skills_list[:3]) if skills_list else '暂无明确技能标签'}"
    
    exp_match_result = '✅ 符合' if '应届' not in work_years else '⚠️ 经验不足'
    
    edu_match_result = '✅ 符合' if edu in ['本科', '硕士', '博士'] else '⚠️ 学历偏低'
    
    location_match_result = '✅ 符合'
    
    table = f"""|匹配维度|匹配情况|详细说明|
|-|-|-|
|技能匹配|{skill_match_result}|{skill_match_desc}|
|经验匹配|{exp_match_result}|工作年限：{work_years or '未知'}|
|学历匹配|{edu_match_result}|{edu or '未知'}|
|地点匹配|{location_match_result}|期望地点：{location or '未知'}|
"""
    
    highlights_list = [
        f"技能{'匹配' if skill_match else '部分匹配'}：{', '.join(skills_list[:3])}" if skills_list else '暂无明确技能亮点',
        f"工作年限{work_years or '未知'}",
        f"{edu or '未知'}学历"
    ]
    highlights = "🌟 " + '\n🌟 '.join([h for h in highlights_list if h])
    

    gaps_list = [
        '技能与岗位要求匹配度需进一步确认' if not skill_match else '暂无明显差距',
        '缺乏正式工作经验' if '应届' in work_years else '暂无'
    ]
    gaps = "📉 " + '\n📉 '.join([g for g in gaps_list if g])
    
    return {'table': table, 'highlights': highlights, 'gaps': gaps}


def generate_interview_suggestions(resume_data, job_title, skills_list, match_score=5.0):
    """生成面试建议，包含合适/不合适结论"""
    if not skills_list:
        skills_str = resume_data.get('技能标签', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
    
    work_years = resume_data.get('工作年限', '')
    status = resume_data.get('当前职业状态', '')
    name = resume_data.get('姓名', '')
    
    # 根据匹配度判断是否合适
    if match_score >= 7.0:
        conclusion = "✅ **合适** - 简历与岗位匹配度较高，建议安排面试"
    elif match_score >= 5.0:
        conclusion = "⚠️ **可考虑** - 匹配度一般，需进一步评估后再决定"
    else:
        conclusion = "❌ **不合适** - 匹配度较低，建议不安排面试"
    
    focus = f"🔹 {', '.join(skills_list[:3]) if skills_list else '岗位相关技能'}掌握程度\n🔹 项目实战经验\n🔹 对平台开发岗位的理解"
    
    questions = f"""❓ 请介绍一下你最熟悉的项目经历？
❓ 你对{job_title}岗位的理解是什么？
❓ {'为什么考虑离职？' if '离职' in status else '目前在职，为何考虑新机会？'}
❓ 你的职业规划是什么？"""
    
    background = f"🔍 {'实习' if '应届' in work_years else '工作'}经历真实性\n🔍 了解实际技术能力\n🔍 {'离职原因和时间' if '离职' in status else '在职稳定性'}"
    
    salary = resume_data.get('期望薪资', '')
    salary_advice = f"💰 期望{salary or '未知'}，需确认是否符合岗位薪资区间" if salary else "💰 薪资期望需在面试中确认"
    
    return {
        'conclusion': conclusion,
        'focus': focus,
        'questions': questions,
        'background': background,
        'salary': salary_advice
    }


def main():
    parser = argparse.ArgumentParser(description='智联招聘详细简历获取')
    parser.add_argument('--name', '-n', required=True, help='候选人姓名')
    parser.add_argument('--job-title', '-j', default='面议', help='应聘岗位（用于搜索）')
    parser.add_argument('--keyword', '-k', default='', help='搜索关键词（岗位名称）')
    parser.add_argument('--location', '-l', default=None, help='工作地点（如：北京、河南-周口）')
    parser.add_argument('--education', '-e', default=None, help='学历要求（如：本科，大专）')
    parser.add_argument('--experience', '-exp', default=None, help='工作经验要求（如：1-3年、3-5年）')
    parser.add_argument('--cookies', help='Cookie字符串')
    parser.add_argument('--output', '-o', help='输出报告路径')
    parser.add_argument('--screenshot', '-s', action='store_true', help='启用截图功能（默认关闭，仅在需要时启用）')
    
    args = parser.parse_args()
    
    # 搜索关键词：如果没传，使用岗位名称
    search_keyword = args.keyword if args.keyword else args.job_title
    
    cookies = args.cookies or load_cookies()
    if cookies is None:
        print("错误：请提供Cookie")
        return 1
    
    resume_data = get_resume_detail_by_name(
        args.name, 
        search_keyword, 
        cookies=cookies,
        location=args.location,
        education=args.education,
        experience=args.experience,
        enable_screenshot=args.screenshot
    )
    
    if resume_data:
        print(f"\n成功获取简历数据: {resume_data.get('姓名', '未知')}")
        
        if args.output:
            output_path = args.output
        else:
            today = datetime.now().strftime('%Y-%m-%d')
            output_path = f"/lhcos-datas/reports/详细报告/简历分析报告-{args.name}-{today}.md"
        
        generate_detail_report(resume_data, args.job_title, output_path)
    else:
        print("获取简历详情失败")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
