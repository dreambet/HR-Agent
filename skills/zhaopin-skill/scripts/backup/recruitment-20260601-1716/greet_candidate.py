#!/usr/bin/env python3
"""
智联招聘主动打招呼脚本

功能：
1. 通过API获取企业职位列表
2. 找到目标候选人卡片
3. 点击"打招呼"按钮
4. 在打招呼弹窗中选择职位并发送

改造记录（2026-05-19）：
- 新增 get_job_list_via_api() 函数，API直调获取职位列表
- 保留最小化浏览器点击：打招呼按钮、选择职位、确定
- 不再依赖点击"沟通职位"输入框触发API

使用方式：
python3 greet_candidate.py --name "候选人姓名" --keyword "岗位名称" --job-select "auto"
"""

import argparse
import os
import sys
import time
import json
import re
from datetime import datetime

from playwright.sync_api import sync_playwright
import requests

# 配置文件路径
COOKIE_FILE = '/root/.openclaw/workspace-HR-Agent/config/zhaopin_cookies.txt'


def get_city_id(city_name):
    """城市名转ID（与search_resumes.py一致）"""
    if not city_name:
        return None
    
    city_map = {
        "周口": 734, "郑州": 701, "北京": 530, "上海": 538,
        "深圳": 765, "广州": 763, "杭州": 653, "南京": 635,
        "东莞": 779, "中山": 780, "成都": 801, "武汉": 736,
        "西安": 854, "长沙": 749, "重庆": 551, "苏州": 639,
        "宝安": 765, "惠州": 773, "清溪": 779,
    }
    
    # 处理 "河南-周口" 格式
    if '-' in city_name:
        parts = city_name.split('-')
        city_name = parts[-1]
    
    return city_map.get(city_name, 734)


def build_filter_params(location=None, education=None, experience=None):
    """构建过滤参数（尽量与search_resumes.py一致）"""
    params = {
        'filteringChatted': False,
        'filteringRead': False,
        'filteringDownloaded': False,
        'filteringOtherChattedType': 'DONT_FILTER',
        'matchLatestWorkExperience': False,
        'searchExperimentalGroup': 'EXPERIMENT',
        'frontExperiment': True,
        'firstPageCacheable': False,
        'freeMaskLimit': False,
        'experiment': '',
        'sort': {'type': 'TIME', 'version': 0},
        'pageSize': 50,
    }
    
    if location:
        city_id = get_city_id(location)
        if city_id:
            params['expectedCityIds'] = [city_id]
    
    if education and '不限' not in education:
        edu_map = {"初中": "9", "初中及以下": "9", "高中": "7", "中专": "12", "中专/中技": "12", "中技": "12", "大专": "5", "本科": "4", "硕士": "3", "博士": "1"}
        edu_levels = [edu_map[e] for e in edu_map if e in education]
        if edu_levels:
            params['educations'] = edu_levels
    elif education:
        params['educations'] = ["4", "3", "10", "1"]
    
    if experience and '不限' not in experience:
        exp_map = {"1年以下": "2", "1-3年": "3", "3-5年": "4", "5-10年": "5", "10年以上": "6"}
        exp_levels = [exp_map[e] for e in exp_map if e in experience]
        if exp_levels:
            params['workingYears'] = exp_levels
    
    return params


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


def load_search_context():
    """从上下文文件加载之前的搜索参数"""
    context_path = '/tmp/zhaopin_search_context.json'
    if not os.path.exists(context_path):
        print(f"错误：搜索上下文文件不存在: {context_path}")
        print("请先运行 search_resumes.py 进行简历搜索")
        return None
    
    try:
        with open(context_path, 'r', encoding='utf-8') as f:
            context = json.load(f)
        
        # 验证必要的字段
        if not context.get('keywords'):
            print("错误：搜索上下文文件中没有关键词")
            return None
        
        print(f"✅ 已加载搜索上下文")
        print(f"   关键词: {context.get('keywords')}")
        print(f"   地点: {context.get('location') or '不限'}")
        print(f"   学历: {context.get('education') or '不限'}")
        print(f"   经验: {context.get('experience') or '不限'}")
        print(f"   候选人数量: {len(context.get('candidates', []))} 人")
        
        # 显示可用候选人列表
        candidates = context.get('candidates', [])
        if candidates:
            print(f"\n   可用候选人:")
            for i, c in enumerate(candidates, 1):
                print(f"   {i}. {c.get('name', '未知')} | {c.get('work_years', '')} | {c.get('education', '')} | {c.get('match_score', '')}")
        
        return context
    except Exception as e:
        print(f"错误：加载搜索上下文失败: {e}")
        return None


def get_candidates_from_context(context=None):
    """从上下文获取候选人列表"""
    if context is None:
        context = load_search_context()
        if context is None:
            return []
    return context.get('candidates', [])


def find_candidates_by_name(candidates, name):
    """根据姓名查找候选人列表"""
    matches = []
    # 精确匹配
    for c in candidates:
        if c.get('name') == name:
            matches.append(c)
    # 如果没有精确匹配，尝试模糊匹配
    if not matches:
        name_pattern = name.replace('先生', '').replace('女士', '')
        for c in candidates:
            cname = c.get('name', '')
            if name_pattern in cname or cname.replace('先生', '').replace('女士', '') == name_pattern:
                matches.append(c)
    return matches


def get_job_list_via_api(keyword=None, page_size=50):
    """
    通过API直调获取企业职位列表
    
    Args:
        keyword: 搜索关键词，用于匹配职位
        page_size: 每页数量
    
    Returns:
        list: 职位列表，每个元素包含 jobTitle, jobNumber 等
    """
    print("\n   [API] 开始获取企业职位列表...")
    
    cookies = load_cookies()
    if not cookies:
        print("   [API] 错误：Cookie为空")
        return []
    
    # 解析Cookie
    cookie_dict = {}
    for cookie_str in cookies.split(';'):
        cookie_str = cookie_str.strip()
        if '=' in cookie_str:
            name, value = cookie_str.split('=', 1)
            cookie_dict[name.strip()] = value.strip()
    
    # 获取必要参数
    timestamp = int(time.time() * 1000)
    client_id = cookie_dict.get('zp_client_id', '17a6cc5d-b91c-4395-9716-11da434c716e')
    page_request_id = cookie_dict.get('zp_page_request_id', f'test-{timestamp}')
    
    # 构建URL
    url = f'https://rd6.zhaopin.com/api/job/list?_={timestamp}&x-zp-page-request-id={page_request_id}&x-zp-client-id={client_id}'
    
    all_jobs = []
    page_no = 1
    max_pages = 10  # 最多获取10页
    
    # 首先尝试用关键词搜索
    if keyword:
        payload = {
            'includingDetail': False,
            'includingHotJob': True,
            'states': ['RELEASED'],
            'query': keyword,
            'pageSize': page_size,
            'pageNo': page_no
        }
        
        try:
            resp = requests.post(
                url, 
                json=payload, 
                cookies=cookie_dict, 
                timeout=15,
                headers={
                    'Content-Type': 'application/json', 
                    'Accept': 'application/json',
                    'Origin': 'https://rd6.zhaopin.com',
                    'Referer': 'https://rd6.zhaopin.com/'
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    jobs = data.get('data', [])
                    if jobs:
                        all_jobs.extend(jobs)
                        print(f"   [API] 关键词'{keyword}'匹配到 {len(jobs)} 个职位")
                        
                        # 如果关键词搜索有结果，直接返回
                        if len(jobs) >= page_size:
                            page_no = 2
                            while page_no <= max_pages:
                                payload['pageNo'] = page_no
                                resp = requests.post(url, json=payload, cookies=cookie_dict, timeout=15,
                                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
                                if resp.status_code == 200 and resp.json().get('code') == 200:
                                    more_jobs = resp.json().get('data', [])
                                    if more_jobs:
                                        all_jobs.extend(more_jobs)
                                        page_no += 1
                                    else:
                                        break
                                else:
                                    break
                            print(f"   [API] 共获取 {len(all_jobs)} 个职位")
                            return all_jobs
        except Exception as e:
            print(f"   [API] 关键词搜索异常: {e}")
    
    # 关键词搜索结果为空或没有关键词，获取所有职位
    if not all_jobs:
        print(f"   [API] 获取全部职位列表...")
        payload = {
            'includingDetail': False,
            'includingHotJob': True,
            'states': ['RELEASED'],
            'query': '',  # 不使用关键词过滤
            'pageSize': page_size,
            'pageNo': 1
        }
        
        while page_no <= max_pages:
            try:
                payload['pageNo'] = page_no
                resp = requests.post(
                    url, 
                    json=payload, 
                    cookies=cookie_dict, 
                    timeout=15,
                    headers={
                        'Content-Type': 'application/json', 
                        'Accept': 'application/json',
                        'Origin': 'https://rd6.zhaopin.com',
                        'Referer': 'https://rd6.zhaopin.com/'
                    }
                )
                
                if resp.status_code != 200:
                    print(f"   [API] 第 {page_no} 页请求失败: HTTP {resp.status_code}")
                    break
                
                data = resp.json()
                if data.get('code') != 200:
                    print(f"   [API] 第 {page_no} 页返回错误: {data.get('message', 'unknown')}")
                    break
                
                jobs = data.get('data', [])
                if not jobs:
                    break
                
                all_jobs.extend(jobs)
                print(f"   [API] 第 {page_no} 页获取 {len(jobs)} 个职位")
                
                # 如果返回数量少于pageSize，说明已经是最后一页
                if len(jobs) < page_size:
                    break
                
                page_no += 1
                
            except Exception as e:
                print(f"   [API] 第 {page_no} 页请求异常: {e}")
                break
    
    print(f"   [API] 共获取 {len(all_jobs)} 个职位")
    return all_jobs


def find_related_jobs(jobs, keyword):
    """
    查找与关键词相关的职位（IT/开发/技术相关）
    """
    if not jobs:
        return []
    
    # IT/开发/技术相关的关键词
    related_keywords = [
        '开发', '软件', 'java', 'python', '前端', '后端', '测试', '运维',
        '网络', '系统', '数据库', 'server', 'devops', '云', '安全',
        '信息', '资讯', 'it', '技术', '工程师', ' programmer', 'developer'
    ]
    
    keyword_lower = keyword.lower()
    related_jobs = []
    
    for job in jobs:
        job_title = job.get('jobTitle', '').lower()
        
        # 检查职位名是否包含相关关键词
        for rel_kw in related_keywords:
            if rel_kw in job_title or rel_kw in keyword_lower and rel_kw in job_title:
                related_jobs.append(job)
                break
    
    return related_jobs


def generate_greeting_message(job_title):
    """
    根据职位生成招呼语消息
    格式：结合匹配到的职位进行生成
    """
    if not job_title:
        return '您好，我对您的简历很感兴趣，希望能有机会沟通。'
    return f"您好，我对您的简历很感兴趣，希望能有机会沟通。我司正在招聘【{job_title}】职位，期待与您进一步沟通。"


def match_job(jobs, keyword):
    """
    根据关键词匹配最合适的职位，优先选择语义相关的职位
    
    特殊规则（2026-05-22）：
    - 软硬件开发类岗位（程序员/开发/软件/硬件等）→ 直接匹配"资讯工程师"
    
    Args:
        jobs: 职位列表
        keyword: 搜索关键词
    
    Returns:
        tuple: (matched_job, match_score, related_jobs)
    """
    if not jobs or not keyword:
        return None, 0, find_related_jobs(jobs, keyword) if jobs else []
    
    keyword_lower = keyword.lower()
    keyword_chars = re.sub(r'[\s\-\/\\]', '', keyword_lower)  # 去除空格和特殊字符
    
    # =====================================================
    # 🎯 硬性映射规则：软硬件开发类岗位 → 资讯工程师
    # 2026-05-22 用户指定规则
    # =====================================================
    dev_keywords = [
        '程序员', '开发', '软件', '硬件', '编程', 'coding',
        '前端', '后端', '全栈', '嵌入式', 'c#', 'c++', 'java',
        'python', 'golang', 'rust', 'php', 'node', 'web',
        'app', '客户端', '服务端', '程序', 'devops',
    ]
    
    is_dev_role = False
    for dev_kw in dev_keywords:
        if dev_kw.lower() in keyword_lower:
            is_dev_role = True
            break
    
    if is_dev_role:
        # 在职位列表中查找"资讯工程师"
        for job in jobs:
            job_title = job.get('jobTitle', '')
            if '资讯工程师' in job_title:
                print(f"   [匹配规则] 软硬件开发岗 → 固定匹配: 资讯工程师")
                return job, 100, []
        # 找不到资讯工程师，继续走正常匹配流程
        print(f"   [匹配规则] 软硬件开发岗但未找到'资讯工程师'，走正常匹配")
    
    # 定义关键词的同义词/相关词分组
    keyword_groups = {
        'it相关': ['软件', '开发', '程序员', '工程师', '技术', 'IT', '资讯', '网络', '系统', '数据', '数据库', '前端', '后端', '全栈', '架构'],
        '制造业': ['CNC', '加工', '车床', '铣床', '模具', '钳工', '技工', '操作工', '工厂'],
        '管理': ['主管', '经理', '总监', '负责人', '组长', ' leader'],
        '人事': ['招聘', 'HR', '人事', '人力资源', '培训', '绩效']
    }
    
    # 找出关键词属于哪个分组
    keyword_group = None
    for group_name, terms in keyword_groups.items():
        for term in terms:
            if term.lower() in keyword_lower:
                keyword_group = group_name
                break
        if keyword_group:
            break
    
    best_match = None
    best_score = 0
    
    for job in jobs:
        job_title = job.get('jobTitle', '').lower()
        job_title_chars = re.sub(r'[\s\-\/\\]', '', job_title)
        
        score = 0
        
        # 完全包含关键词
        if keyword_lower in job_title:
            score = 100
        # 关键词包含职位名
        elif job_title in keyword_lower:
            score = 90
        # 去除特殊字符后匹配
        elif keyword_chars in job_title_chars:
            score = 80
        elif job_title_chars in keyword_chars:
            score = 70
        # 检查是否在同一分组（语义相关）
        elif keyword_group:
            job_group = None
            for group_name, terms in keyword_groups.items():
                for term in terms:
                    if term.lower() in job_title:
                        job_group = group_name
                        break
                if job_group:
                    break
            
            # 如果在同一分组，给予较高分数
            if job_group == keyword_group:
                score = 75
                # IT相关分组内，更喜欢包含"工程师"的职位
                if keyword_group == 'it相关' and '工程师' in job.get('jobTitle', ''):
                    score = 85
            # IT相关关键词匹配到非IT职位，给予低分
            elif keyword_group == 'it相关':
                score = 20
        # 部分字符匹配
        else:
            # 检查关键词中的主要字符是否都在职位名中
            kw_chars = set(keyword_chars)
            jt_chars = set(job_title_chars)
            common = kw_chars & jt_chars
            if common and len(common) / len(kw_chars) > 0.6:
                score = 50
        
        if score > best_score:
            best_score = score
            best_match = job
    
    # 如果最佳匹配分数低于50，查找相关职位
    related_jobs = []
    if best_score < 50:
        related_jobs = find_related_jobs(jobs, keyword)
    
    return best_match, best_score, related_jobs


def close_novice_guide(page):
    """检测并关闭新手引导弹窗"""
    print("   [UI] 检测新手引导弹窗...")
    try:
        close_selectors = [
            'button:has-text("关闭")',
            'button:has-text("我知道啦")',
            'button:has-text("我知道了")',
            '[class*="novice-guide"] button',
            '[class*="guide"] [class*="close"]',
            '.km-popover button'
        ]
        
        for selector in close_selectors:
            btns = page.locator(selector).all()
            for btn in btns:
                try:
                    text = btn.text_content() or ''
                    if '关闭' in text or '知道' in text or '不再' in text:
                        if btn.is_visible():
                            btn.click()
                            print("   [UI] 已关闭新手引导弹窗")
                            page.wait_for_timeout(500)
                            return True
                except:
                    pass
        
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        page.click('body', position={'x': 10, 'y': 10})
        page.wait_for_timeout(300)
        print("   [UI] 已尝试关闭弹窗")
        return True
    except Exception as e:
        print(f"   [UI] 关闭弹窗失败: {e}")
        return False


def find_candidate_on_page(page, candidate_name, candidate_info=None):
    """
    在当前页面查找候选人卡片
    
    Args:
        page: Playwright page object
        candidate_name: 候选人姓名
        candidate_info: 候选人其他信息，用于更精确匹配
            {
                'age': '25岁',
                'work_years': '3年',
                'education': '本科',
                'resume_number': 'xxx'
            }
    """
    # 构建匹配文本（姓名 + 年龄 + 工作年限）
    match_hints = [candidate_name]
    if candidate_info:
        if candidate_info.get('age'):
            match_hints.append(candidate_info['age'])
        if candidate_info.get('work_years'):
            match_hints.append(candidate_info['work_years'])
        if candidate_info.get('education'):
            match_hints.append(candidate_info['education'])
    
    result = page.evaluate('''(params) => {
        const candidateName = params.candidateName;
        const matchHints = params.matchHints;
        
        // =====================================================
        // 🛡️ 精确选择器：仅匹配独立候选人卡片，排除外层容器
        // 
        // 智联招聘真实DOM结构:
        //   search-resume-list (容器 - 包含所有候选人)
        //   └── search-resume-item-wrap (每个候选人的wrapper)
        //       └── search-resume-item.resume-item-exp (卡片本体)
        //           ├── 姓名、经历等
        //           └── 打招呼按钮
        //
        // ❌ 禁止使用 [class*="card"] 或 [class*="item"]
        //    它们会匹配容器(search-resume-list)，其textContent包含
        //    所有候选人名字，导致点错人！
        // =====================================================
        
        let cards = document.querySelectorAll('.search-resume-item-wrap');
        if (cards.length === 0) {
            cards = document.querySelectorAll('.search-resume-item.resume-item-exp');
        }
        
        let result = {
            found: false,
            cardIndex: -1,
            greetButtonFound: false,
            cardName: '',
            error: '',
            totalCards: cards.length
        };
        
        if (cards.length === 0) {
            result.error = 'No candidate cards found on page (selector .search-resume-item-wrap returned 0)';
            return result;
        }
        
        // 精确匹配：姓名必须完全匹配
        // 其他提示（年龄、工作年限、学历）作为辅助验证
        
        // 增强：收集所有姓名匹配的卡片，再用辅助字段严格筛选
        const nameMatchingCards = [];
        for (let i = 0; i < cards.length; i++) {
            const card = cards[i];
            const text = card.textContent || '';
            
            // 首先检查：姓名是否完全匹配（主要条件）
            const namePatterns = [
                candidateName,
                candidateName + ' ',
                candidateName.replace(/先生|女士/, ' ')
            ];
            
            let nameMatch = false;
            for (const pattern of namePatterns) {
                if (text.includes(pattern)) {
                    nameMatch = true;
                    break;
                }
            }
            
            if (!nameMatch) {
                continue;
            }
            
            // 姓名匹配后，检查所有辅助字段匹配情况
            let matchedHints = [];
            let unmatchedHints = [];
            
            for (const hint of matchHints) {
                if (hint === candidateName) continue;
                if (text.includes(hint)) {
                    matchedHints.push(hint);
                } else {
                    unmatchedHints.push(hint);
                }
            }
            
            nameMatchingCards.push({
                index: i,
                card: card,
                matchedHints: matchedHints,
                unmatchedHints: unmatchedHints,
                text: text
            });
        }
        
        // 增强策略：从所有姓名匹配卡片中，优先选择辅助字段匹配最多的
        // 如果有辅助字段信息，优先选择辅助字段匹配最多的卡片
        let chosenCard = null;
        if (nameMatchingCards.length === 0) {
            result.error = 'Candidate card not found';
            return result;
        } else if (nameMatchingCards.length === 1) {
            // 只有一个姓名匹配，直接使用
            chosenCard = nameMatchingCards[0];
        } else {
            // 多个姓名匹配（如同名候选人），优先选辅助字段匹配最多的
            nameMatchingCards.sort((a, b) => b.matchedHints.length - a.matchedHints.length);
            const bestMatch = nameMatchingCards[0];
            if (bestMatch.matchedHints.length > 0) {
                chosenCard = bestMatch;
                console.log('Same-name deduplication: selected card with', bestMatch.matchedHints.length, 'matched hints');
            } else {
                // 没有辅助字段匹配，只能选第一个（记录警告）
                chosenCard = nameMatchingCards[0];
                console.warn('Same-name warning: multiple cards match name but no auxiliary fields to differentiate');
            }
        }
        
        if (chosenCard) {
            result.found = true;
            result.cardIndex = chosenCard.index;
            result.cardName = candidateName;
            result.matchedHints = chosenCard.matchedHints;
            result.unmatchedHints = chosenCard.unmatchedHints;
            
            // 查找并点击打招呼按钮
            const buttons = chosenCard.card.querySelectorAll('button');
            for (const btn of buttons) {
                const btnText = btn.textContent.trim();
                if (btnText.includes('打招呼') || btnText.includes('聊一聊')) {
                    result.greetButtonFound = true;
                    btn.scrollIntoViewIfNeeded();
                    btn.click();
                    break;
                }
            }
        }
        
        if (!result.found) {
            result.error = 'Candidate card not found';
        } else if (!result.greetButtonFound) {
            result.error = 'Greet button not found on card';
        }
        
        return result;
    }''', {'candidateName': candidate_name, 'matchHints': match_hints})
    return result


def has_next_page(page):
    """检查是否有下一页（修复：使用query_selector直接查DOM）"""
    try:
        next_arrow = page.query_selector('.km-pagination__pager--arrow:not(.km-pagination__pager--disabled)')
        if next_arrow:
            return True
        all_buttons = page.query_selector_all('button')
        for btn in all_buttons:
            text = (btn.text_content() or '').strip()
            if '下一页' in text or '下页' in text:
                disabled = btn.get_attribute('disabled')
                if disabled is None:
                    return True
        return False
    except:
        return False


def click_next_page(page):
    """点击下一页（修复：使用JS点击避免元素不可见问题）"""
    try:
        next_arrow = page.query_selector('.km-pagination__pager--arrow:not(.km-pagination__pager--disabled)')
        if next_arrow:
            page.evaluate('(el) => el.click()', next_arrow)
            page.wait_for_timeout(2500)
            return True
        all_buttons = page.query_selector_all('button')
        for btn in all_buttons:
            text = (btn.text_content() or '').strip()
            if '下一页' in text or '下页' in text:
                disabled = btn.get_attribute('disabled')
                if disabled is None:
                    page.evaluate('(el) => el.click()', btn)
                    page.wait_for_timeout(2500)
                    return True
        return False
    except:
        return False


def greet_candidate(candidate_name, job_keyword, cookies=None, location=None, education=None, experience=None, screenshot=False, candidate_info=None):
    """
    对指定候选人发送打招呼消息（改造版）
    
    流程：
    1. 浏览器打开搜索页面
    2. 输入关键词搜索
    3. 分页找到目标候选人（使用姓名+年龄+工作年限等多字段匹配）
    4. 点击打招呼按钮
    5. 弹窗出现后，通过API获取职位列表
    6. 选择匹配的职位
    7. 点击确定发送
    
    Args:
        candidate_name: 候选人姓名
        job_keyword: 岗位关键词
        candidate_info: 候选人详细信息，用于更精确匹配
            {
                'age': '25岁',
                'work_years': '3年',
                'education': '本科',
                'resume_number': 'xxx'
            }
    """
    if cookies is None:
        cookies = load_cookies()
        if cookies is None:
            return None
    
    print(f"\n开始向候选人 '{candidate_name}' 发送打招呼消息...")
    print(f"岗位关键词: {job_keyword}")
    if location:
        print(f"地点筛选: {location}")
    
    debug_dir = "/tmp/zhaopin_debug"
    os.makedirs(debug_dir, exist_ok=True)
    
    # 第一步：通过API获取职位列表
    print("\n[Step 0] 获取企业职位列表...")
    jobs = get_job_list_via_api(keyword=job_keyword)
    
    # 存储可用职位列表用于后续选择
    available_jobs_for_selection = []
    
    if jobs:
        matched_job, match_score, related_jobs = match_job(jobs, job_keyword)
        
        if matched_job and match_score >= 50:
            print(f"   [API] 匹配到职位: {matched_job.get('jobTitle')} (分数: {match_score})")
            print(f"   [API] 职位编号: {matched_job.get('jobNumber')}")
        elif related_jobs:
            print(f"   [API] 未找到与'{job_keyword}'完全匹配的职位")
            print(f"   [API] 找到 {len(related_jobs)} 个相关职位:")
            for i, job in enumerate(related_jobs[:5], 1):
                print(f"   [API]   {i}. {job.get('jobTitle')}")
            # 使用第一个相关职位
            matched_job = related_jobs[0]
            available_jobs_for_selection = related_jobs[1:]  # 剩余的作为备选
            print(f"   [API] 将使用相关职位: {matched_job.get('jobTitle')}")
        else:
            print(f"   [API] 未找到与'{job_keyword}'相关的职位")
            print(f"   [API] 共有 {len(jobs)} 个职位可选")
            # 显示前10个职位
            for i, job in enumerate(jobs[:10], 1):
                print(f"   [API]   {i}. {job.get('jobTitle')}")
            # 选择第一个职位作为兜底
            matched_job = jobs[0] if jobs else None
            available_jobs_for_selection = jobs[1:10]  # 剩余的作为备选
            if matched_job:
                print(f"   [API] 将使用第一个职位: {matched_job.get('jobTitle')}")
    else:
        print(f"   [API] 获取职位列表失败或为空")
        matched_job = None
    
    if screenshot:
        print(f"   [调试] 职位列表已获取，共 {len(jobs)} 个")
    
    target_found = False
    greet_button_clicked = False
    current_page = 1
    max_pages = 20
    greet_result = {'found': False}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context()
            
            # 设置Cookie
            cookie_list = []
            for cookie_str in cookies.split(';'):
                cookie_str = cookie_str.strip()
                if '=' in cookie_str:
                    name, value = cookie_str.split('=', 1)
                    try:
                        cookie_list.append({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.rd6.zhaopin.com',
                            'path': '/'
                        })
                    except:
                        pass
            context.add_cookies(cookie_list)
            
            page = context.new_page()

            # 增强：拦截搜索API请求，注入与初筛报告一致的过滤/排序参数。
            # 这样初筛报告中的候选人更容易出现在打招呼页面结果中，避免只搜到页面默认结果。
            filter_params = build_filter_params(location, education, experience)
            if filter_params:
                print(f"   [增强] 注入搜索过滤参数: {filter_params}")

                def handle_search_route(route):
                    request = route.request
                    if '/api/talent/search/list' not in request.url:
                        route.continue_()
                        return
                    try:
                        post_data = request.post_data
                        data = json.loads(post_data) if post_data else {}
                        for key, value in filter_params.items():
                            data[key] = value
                        if job_keyword:
                            data['keywordIntentions'] = [{'keyword': job_keyword}]
                            data['keyword'] = job_keyword
                        # 兼容页面可能使用 pageIndex，初筛API使用 pageNo；两者保持一致。
                        current_page_no = data.get('pageNo') or data.get('pageIndex') or 1
                        data['pageNo'] = current_page_no
                        data['pageIndex'] = current_page_no
                        data['pageSize'] = 50
                        route.continue_(post_data=json.dumps(data, ensure_ascii=False))
                    except Exception as e:
                        print(f"   [增强] 搜索请求注入失败: {e}")
                        route.continue_()

                page.route("**/api/talent/search/list**", handle_search_route)
            
            # 访问搜索页面
            print("\n[Step 1] 访问搜索页面...")
            page.goto("https://rd6.zhaopin.com/app/search", timeout=30000)
            page.wait_for_timeout(2000)
            if screenshot:
                page.screenshot(path=f"{debug_dir}/greet_01_search_page.png")
            
            # 输入岗位关键词
            print("\n[Step 2] 输入岗位关键词...")
            keyword_input = page.locator('input[class*="keyword"]').first
            if keyword_input.count() > 0:
                keyword_input.fill(job_keyword)
            else:
                keyword_input = page.locator('input[placeholder*="岗位"]').first
                if keyword_input.count() > 0:
                    keyword_input.fill(job_keyword)
            page.wait_for_timeout(500)
            if screenshot:
                page.screenshot(path=f"{debug_dir}/greet_02_keyword.png")
            
            # 点击搜索按钮
            print("\n[Step 3] 点击搜索...")
            search_btn = page.locator('button:has-text("搜索"), button:has-text("搜 索")').first
            if search_btn.count() > 0:
                search_btn.click()
            else:
                page.evaluate('''() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.trim();
                        if (text === '搜 索' || text === '搜索') {
                            btn.click();
                            break;
                        }
                    }
                }''')
            
            print("\n[Step 4] 等待搜索结果...")
            page.wait_for_timeout(8000)
            if screenshot:
                page.screenshot(path=f"{debug_dir}/greet_03_search_results.png")
            
            # 分页查找候选人
            print(f"\n[Step 5] 开始分页查找候选人 '{candidate_name}'...")
            
            while current_page <= max_pages:
                print(f"   第 {current_page} 页搜索...")
                
                greet_result = find_candidate_on_page(page, candidate_name, candidate_info)
                
                if greet_result.get('found'):
                    print(f"   ✅ 在第 {current_page} 页找到候选人!")
                    
                    if greet_result.get('greetButtonFound'):
                        print(f"   ✅ 点击了打招呼按钮")
                        greet_button_clicked = True
                    else:
                        print(f"   ⚠️ 未找到打招呼按钮: {greet_result.get('error')}")
                        if screenshot:
                            page.screenshot(path=f"{debug_dir}/greet_03_no_greet_button.png")
                    break
                else:
                    print(f"   ⚠️ 在第 {current_page} 页未找到候选人")
                    # 增强：智联搜索结果可能是虚拟列表，API一页有50条，但DOM只渲染当前可视区域。
                    # 对初筛报告中靠后的候选人，需要滚动列表后继续查找。
                    for scroll_attempt in range(1, 13):
                        print(f"   [增强] 滚动列表继续查找... ({scroll_attempt}/12)")
                        try:
                            page.evaluate('''() => {
                                const selectors = [
                                    '.search-resume-list',
                                    '[class*="search-resume-list"]',
                                    '[class*="resume-list"]',
                                    '[class*="list"]'
                                ];
                                let scrolled = false;
                                for (const sel of selectors) {
                                    const el = document.querySelector(sel);
                                    if (el && el.scrollHeight > el.clientHeight) {
                                        el.scrollTop = el.scrollTop + Math.floor(el.clientHeight * 0.85);
                                        scrolled = true;
                                        break;
                                    }
                                }
                                if (!scrolled) {
                                    window.scrollBy(0, Math.floor(window.innerHeight * 0.85));
                                }
                            }''')
                            page.wait_for_timeout(900)
                            greet_result = find_candidate_on_page(page, candidate_name, candidate_info)
                            if greet_result.get('found'):
                                print(f"   ✅ 滚动后找到候选人! scroll_attempt={scroll_attempt}")
                                if greet_result.get('greetButtonFound'):
                                    print(f"   ✅ 点击了打招呼按钮")
                                    greet_button_clicked = True
                                else:
                                    print(f"   ⚠️ 未找到打招呼按钮: {greet_result.get('error')}")
                                break
                        except Exception as e:
                            print(f"   [增强] 滚动查找异常: {e}")
                            break
                    if greet_result.get('found'):
                        break
                
                
                print(f"   前往第 {current_page + 1} 页...")
                if not click_next_page(page):
                    print(f"   无法前往下一页")
                    break
                
                current_page += 1
                page.wait_for_timeout(3000)
                if screenshot:
                    page.screenshot(path=f"{debug_dir}/greet_04_page_{current_page}.png")
            
            if not greet_result.get('found'):
                print(f"\n   ❌ 在所有 {current_page} 页中都未找到候选人")
                if screenshot:
                    page.screenshot(path=f"{debug_dir}/greet_04_candidate_not_found.png")
                browser.close()
                return None
            
            # 等待打招呼弹窗出现
            if greet_button_clicked:
                print("\n[Step 6] 等待打招呼弹窗...")
                page.wait_for_timeout(3000)
                if screenshot:
                    page.screenshot(path=f"{debug_dir}/greet_05_greet_dialog.png")
                
                # 检查弹窗类型
                dialog_check = page.evaluate('''() => {
                    const dialogs = document.querySelectorAll('[class*="dialog"], [class*="modal"], [role="dialog"]');
                    let result = {
                        hasPurchaseDialog: false,
                        hasKeywordDialog: false,
                        hasGreetDialog: false,
                        hasAIGreetDialog: false,
                        message: ""
                    };
                    
                    for (const d of dialogs) {
                        const text = d.textContent || '';
                        const style = window.getComputedStyle(d);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        
                        // AI招呼语对话框（优先检测：新Cookie直接弹出）
                        if (text.indexOf('AI招呼语') !== -1 || text.indexOf('使用并发送') !== -1) {
                            result.hasAIGreetDialog = true;
                            result.message = "发现AI招呼语对话框";
                        }
                        // 关键词选择对话框
                        if (text.indexOf('请选择关键词') !== -1 || text.indexOf('关键词选择') !== -1) {
                            result.hasKeywordDialog = true;
                            result.message = "发现关键词选择对话框";
                        }
                        // 道具购买对话框
                        if (text.indexOf('聊天权益') !== -1 || text.indexOf('搜索聊加油包') !== -1) {
                            result.hasPurchaseDialog = true;
                            result.message = "发现道具购买对话框";
                        }
                        // 打招呼对话框 - 包含"打招呼"或者"选择沟通职位"
                        if ((text.indexOf('打招呼') !== -1 && text.indexOf('消息') !== -1) || 
                            text.indexOf('选择沟通职位') !== -1) {
                            result.hasGreetDialog = true;
                            result.message = "发现打招呼对话框";
                        }
                    }
                    return result;
                }''')
                
                print(f"   弹窗检查: {dialog_check}")
                
                if dialog_check.get('hasPurchaseDialog'):
                    print(f"   ⚠️ 发现道具购买对话框，账号可能没有足够的聊天权益")
                    browser.close()
                    return None
                
                # AI招呼语对话框处理（新Cookie直接弹出此对话框）
                if dialog_check.get('hasAIGreetDialog'):
                    print(f"   ℹ️ 发现AI招呼语对话框，直接发送招呼语...")
                    try:
                        send_result = page.evaluate("""() => {
                            const buttons = document.querySelectorAll('button');
                            for (const btn of buttons) {
                                const text = btn.textContent.trim();
                                if (text.includes('使用并发送') || text.includes('发送')) {
                                    btn.click();
                                    return { success: true, text: text };
                                }
                            }
                            return { success: false, error: '未找到发送按钮' };
                        }""")
                        if send_result.get('success'):
                            print(f"   ✅ 点击'使用并发送'成功: {send_result.get('text')}")
                            page.wait_for_timeout(2000)
                            remaining = page.evaluate("document.querySelectorAll('.km-modal__wrapper').length")
                            if remaining == 0:
                                print(f"   ✅ 对话框已关闭，打招呼完成!")
                                greet_button_clicked = True
                                target_found = True
                                browser.close()
                                print(f"\n✅ 成功向 {candidate_name} 发送打招呼消息!")
                                return True
                        else:
                            print(f"   ⚠️ 发送失败: {send_result.get('error')}")
                    except Exception as e:
                        print(f"   ⚠️ AI招呼语处理异常: {e}")
                
                if dialog_check.get('hasKeywordDialog'):
                    print(f"   ℹ️ 发现关键词选择对话框")
                    keyword_selected = page.evaluate('''() => {
                        const options = document.querySelectorAll('li');
                        for (const li of options) {
                            const text = li.textContent.trim();
                            if (text && text.length > 2 && text.length < 50) {
                                li.click();
                                return { success: true, text: text };
                            }
                        }
                        return { success: false };
                    }''')
                    
                    if keyword_selected.get('success'):
                        print(f"   ✅ 已选择关键词: {keyword_selected.get('text')}")
                    
                    # 点击确定按钮
                    print(f"   点击确定按钮...")
                    confirm_result = page.evaluate('''() => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            const text = btn.textContent.trim();
                            if (text === '确定' || text === '确认') {
                                const style = window.getComputedStyle(btn);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {
                                    btn.click();
                                    return { success: true, text: text };
                                }
                            }
                        }
                        return { success: false, error: '确定按钮未找到' };
                    }''')
                    
                    if confirm_result.get('success'):
                        print(f"   ✅ 已点击确定")
                    else:
                        print(f"   ⚠️ 点击确定失败: {confirm_result.get('error')}")
                    
                    # 点击确定后，等待打招呼弹窗出现
                    print(f"   等待打招呼弹窗出现...")
                    page.wait_for_timeout(2000)
                    
                    # 循环检查直到打招呼弹窗出现或超时
                    max_wait = 10
                    wait_count = 0
                    greet_dialog_found = False
                    
                    while wait_count < max_wait:
                        dialog_check2 = page.evaluate('''() => {
                            const dialogs = document.querySelectorAll('[class*="dialog"], [class*="modal"], [role="dialog"]');
                            for (const d of dialogs) {
                                const text = d.textContent || '';
                                const style = window.getComputedStyle(d);
                                if (style.display === 'none' || style.visibility === 'hidden') continue;
                                
                                if ((text.indexOf('打招呼') !== -1 && text.indexOf('消息') !== -1) || 
                                    text.indexOf('选择沟通职位') !== -1) {
                                    return { found: true, text: text.substring(0, 200) };
                                }
                            }
                            return { found: false };
                        }''')
                        
                        if dialog_check2.get('found'):
                            print(f"   ✅ 打招呼弹窗已出现")
                            greet_dialog_found = True
                            break
                        
                        wait_count += 1
                        print(f"   等待弹窗出现... ({wait_count}/{max_wait})")
                        page.wait_for_timeout(1000)
                    
                    if not greet_dialog_found:
                        print(f"   ⚠️ 等待打招呼弹窗超时，尝试重新点击打招呼按钮...")
                        # 🛡️ 修复：使用精确选择器+动态候选人姓名，不再硬编码
                        retry_match_hints = [candidate_name]
                        if candidate_info:
                            if candidate_info.get('age'):
                                retry_match_hints.append(candidate_info['age'])
                            if candidate_info.get('work_years'):
                                retry_match_hints.append(candidate_info['work_years'])
                        
                        retry_result = page.evaluate('''(params) => {
                            const candidateName = params.candidateName;
                            const matchHints = params.matchHints;
                            
                            let cards = document.querySelectorAll('.search-resume-item-wrap');
                            if (cards.length === 0) {
                                cards = document.querySelectorAll('.search-resume-item.resume-item-exp');
                            }
                            
                            for (const card of cards) {
                                const text = card.textContent || '';
                                // 动态匹配：使用传入的候选人姓名和辅助提示
                                let nameMatch = false;
                                const namePatterns = [
                                    candidateName,
                                    candidateName + ' ',
                                    candidateName.replace(/先生|女士/, ' ')
                                ];
                                for (const pattern of namePatterns) {
                                    if (text.indexOf(pattern) !== -1) {
                                        nameMatch = true;
                                        break;
                                    }
                                }
                                
                                if (!nameMatch) continue;
                                
                                // 交叉验证：至少匹配一个辅助提示
                                let hintMatch = matchHints.length <= 1;
                                for (const hint of matchHints) {
                                    if (hint !== candidateName && text.indexOf(hint) !== -1) {
                                        hintMatch = true;
                                        break;
                                    }
                                }
                                
                                if (!hintMatch) continue;
                                
                                const buttons = card.querySelectorAll('button');
                                for (const btn of buttons) {
                                    const btnText = btn.textContent.trim();
                                    if (btnText.indexOf('打招呼') !== -1 || btnText.indexOf('聊一聊') !== -1) {
                                        btn.scrollIntoViewIfNeeded();
                                        btn.click();
                                        return { success: true, clicked: true, cardText: text.substring(0, 100) };
                                    }
                                }
                            }
                            return { success: false, clicked: false };
                        }''', {'candidateName': candidate_name, 'matchHints': retry_match_hints})
                        
                        if retry_result.get('success'):
                            print(f"   ✅ 重新点击了打招呼按钮")
                            page.wait_for_timeout(3000)
                            
                            # 再次检查打招呼弹窗
                            for i in range(5):
                                dialog_check3 = page.evaluate('''() => {
                                    const dialogs = document.querySelectorAll('[class*="dialog"], [class*="modal"], [role="dialog"]');
                                    for (const d of dialogs) {
                                        const text = d.textContent || '';
                                        const style = window.getComputedStyle(d);
                                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                                        if ((text.indexOf('打招呼') !== -1 && text.indexOf('消息') !== -1) || 
                                            text.indexOf('选择沟通职位') !== -1) {
                                            return { found: true };
                                        }
                                    }
                                    return { found: false };
                                }''')
                                
                                if dialog_check3.get('found'):
                                    print(f"   ✅ 重新点击后打招呼弹窗出现了!")
                                    greet_dialog_found = True
                                    break
                                page.wait_for_timeout(1000)
                        
                        if screenshot:
                            page.screenshot(path=f"{debug_dir}/greet_05c_timeout.png")
                    
                    if not greet_dialog_found:
                        print(f"   ⚠️ 等待打招呼弹窗超时")
                
                # ============================================
                # 处理打招呼弹窗 - 选择职位并发送
                # ============================================
                print("\n[Step 7] 处理打招呼弹窗...")
                
                # 使用API获取的职位数据进行选择
                if matched_job:
                    job_title = matched_job.get('jobTitle', '')
                    job_number = matched_job.get('jobNumber', '')
                    print(f"   [职位] 将选择: {job_title} (编号: {job_number})")
                
                # 点击沟通职位输入框打开下拉列表
                print("   [UI] 点击沟通职位输入框...")
                click_input_result = page.evaluate("""() => {
                    // 查找沟通职位输入框
                    const inputs = document.querySelectorAll('input, textarea');
                    let targetInput = null;
                    
                    for (const inp of inputs) {
                        const placeholder = inp.placeholder || '';
                        const title = inp.title || '';
                        if (placeholder.includes('沟通职位') || title.includes('沟通职位')) {
                            targetInput = inp;
                            break;
                        }
                    }
                    
                    if (!targetInput) {
                        return { success: false, error: '沟通职位输入框未找到' };
                    }
                    
                    // 点击输入框打开下拉列表
                    targetInput.click();
                    return { success: true, action: 'clicked' };
                }""")
                
                if click_input_result.get('success'):
                    print(f"   ✅ 已点击输入框")
                    page.wait_for_timeout(1500)
                    if screenshot:
                        page.screenshot(path=f"{debug_dir}/greet_05b_dropdown_open.png")
                else:
                    print(f"   ⚠️ 点击输入框失败: {click_input_result.get('error')}")
                    # 尝试直接点击输入框右侧区域
                    page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input');
                        for (const inp of inputs) {
                            const placeholder = inp.placeholder || '';
                            if (placeholder.includes('沟通职位')) {
                                const rect = inp.getBoundingClientRect();
                                const x = rect.right - 20;
                                const y = rect.top + rect.height / 2;
                                document.elementFromPoint(x, y)?.click();
                                break;
                            }
                        }
                    }""")
                    page.wait_for_timeout(1000)
                
                # 选择职位选项 - 使用搜索输入框过滤
                if matched_job:
                    job_title = matched_job.get('jobTitle', '')
                    print(f"   [UI] 选择职位: {job_title}")
                    
                    # 等待下拉列表出现
                    page.wait_for_timeout(1000)
                    
                    try:
                        # 等待下拉容器出现
                        page.wait_for_selector('.km-select__dropdown', timeout=5000)
                        print(f"   [UI] 找到下拉容器 .km-select__dropdown")
                        
                        # 查找搜索输入框并输入关键词
                        search_input = page.locator('.km-select__search .km-input__original')
                        if search_input.count() > 0:
                            print(f"   [UI] 在搜索框中输入职位关键词: {job_title}")
                            search_input.click()
                            search_input.fill(job_title)
                            page.wait_for_timeout(800)  # 等待过滤结果
                        else:
                            print(f"   [UI] 未找到搜索输入框，尝试点击输入框")
                            page.locator('.km-select__search').click()
                            page.wait_for_timeout(500)
                        
                        # 等待并查找过滤后的选项
                        page.wait_for_timeout(500)
                        option_containers = page.locator('.jsn-job-selector__option--container').all()
                        print(f"   [UI] 过滤后找到 {len(option_containers)} 个选项")
                        
                        selected = False
                        for opt in option_containers:
                            try:
                                title_el = opt.locator('.jsn-job-selector__option--title')
                                if title_el.count() > 0:
                                    option_title = title_el.text_content()
                                    print(f"   [UI] 检查选项: {option_title}")
                                    
                                    # 精确匹配
                                    if job_title.strip() == option_title.strip():
                                        opt.click()
                                        print(f"   ✅ 精确匹配选中: {option_title}")
                                        selected = True
                                        break
                                    # 部分匹配
                                    elif job_title.strip() in option_title.strip() or option_title.strip() in job_title.strip():
                                        opt.click()
                                        print(f"   ✅ 部分匹配选中: {option_title}")
                                        selected = True
                                        break
                            except Exception as e:
                                continue
                        
                        if not selected and len(option_containers) > 0:
                            # 选择第一个可见选项
                            first_opt = option_containers[0]
                            title_el = first_opt.locator('.jsn-job-selector__option--title')
                            if title_el.count() > 0:
                                first_title = title_el.text_content()
                                if first_title and first_title.strip():
                                    first_opt.click()
                                    print(f"   ✅ 选择第一个选项: {first_title}")
                                    selected = True
                        
                        if selected:
                            select_result = {'success': True}
                        else:
                            print(f"   ⚠️ 未找到匹配的职位")
                            select_result = {'success': False, 'error': '未找到匹配职位'}
                    except Exception as e:
                        print(f"   [UI] 选择器失败: {e}")
                        select_result = {'success': False, 'error': str(e)}
                else:
                    # 没有API数据，使用关键词选择
                    select_result = page.evaluate(f"""(keyword) => {{
                        const optionSelectors = [
                            '[class*="dropdown-menu"] li',
                            '[class*="select-menu"] li',
                            '[class*="option-list"] li',
                            'li[class*="item"]',
                            '[role="option"]'
                        ];
                        
                        let options = [];
                        for (const sel of optionSelectors) {{
                            const found = document.querySelectorAll(sel);
                            if (found.length > 0) {{
                                options = Array.from(found).map(el => ({{
                                    text: el.textContent.trim(),
                                    element: el
                                }}));
                                break;
                            }}
                        }}
                        
                        if (options.length === 0) {{
                            return {{ success: false, error: '下拉选项未找到' }};
                        }}
                        
                        // 尝试用关键词匹配
                        let selectedOption = null;
                        for (const opt of options) {{
                            if (opt.text.includes(keyword)) {{
                                selectedOption = opt;
                                break;
                            }}
                        }}
                        
                        if (!selectedOption) {{
                            for (const opt of options) {{
                                if (!opt.text.includes('请选择') && opt.text.length > 2) {{
                                    selectedOption = opt;
                                    break;
                                }}
                            }}
                        }}
                        
                        if (selectedOption) {{
                            selectedOption.element.click();
                            return {{ success: true, selected: selectedOption.text }};
                        }}
                        
                        return {{ success: false, error: '无可用选项' }};
                    }}""", job_keyword)
                
                if select_result.get('success'):
                    print(f"   ✅ 已选择岗位")
                    page.wait_for_timeout(500)
                    
                    # 点击确定按钮关闭选择职位对话框
                    print("   [UI] 点击确定按钮...")
                    try:
                        # 使用JavaScript在对话框内查找确定按钮
                        js_result = page.evaluate("""() => {
                            // 查找对话框
                            const modal = document.querySelector('.km-modal__wrapper');
                            if (!modal) return { success: false, error: '未找到对话框' };
                            
                            // 在对话框内查找确定按钮
                            const buttons = modal.querySelectorAll('button');
                            for (const btn of buttons) {
                                const txt = btn.textContent.trim();
                                if (txt === '确定' || txt.includes('确定')) {
                                    btn.click();
                                    return { success: true, text: txt };
                                }
                            }
                            return { success: false, error: '未找到确定按钮' };
                        }""")
                        
                        print(f"   [UI] JavaScript点击结果: {js_result}")
                        
                        if js_result.get('success'):
                            print("   [UI] 已点击确定，等待对话框变化...")
                            page.wait_for_timeout(2000)
                            
                            # 截图查看当前状态
                            if screenshot:
                                page.screenshot(path=f"{debug_dir}/greet_08_after_confirm.png")
                            
                            # 检查是否出现了招呼语设置对话框（优先查找模态框）
                            modal_check = page.evaluate("""() => {
                                const modals = document.querySelectorAll('.km-modal__wrapper');
                                for (const m of modals) {
                                    const text = m.innerText || '';
                                    if (text.includes('AI招呼语') || text.includes('使用并发送')) {
                                        return { found: true, text: text.substring(0, 100) };
                                    }
                                }
                                const bodyText = document.body.innerText;
                                if (bodyText.includes('AI招呼语') || bodyText.includes('使用并发送')) {
                                    return { found: true, source: 'body', text: bodyText.substring(0, 100) };
                                }
                                return { found: false };
                            }""")
                            if modal_check.get("found"):
                                print(f"   ✅ 检测到招呼语设置对话框")
                                
                                # 切换到"自己设置招呼语"（如果需要）
                                print("   [UI] 检查是否需要切换到'自己设置招呼语'...")
                                try:
                                    # 查找并点击"自己设置招呼语"选项/标签
                                    switch_result = page.evaluate("""() => {
                                        // 查找所有可能包含"自己设置招呼语"的元素
                                        const allElements = document.querySelectorAll('*');
                                        for (const el of allElements) {
                                            if (el.childNodes.length === 1 && el.textContent.trim() === '自己设置招呼语') {
                                                el.click();
                                                return { success: true, action: 'clicked element with text' };
                                            }
                                        }
                                        
                                        // 尝试查找包含这个文字的链接或按钮
                                        const links = document.querySelectorAll('a, button, [role=\"tab\"]');
                                        for (const link of links) {
                                            if (link.textContent.trim() === '自己设置招呼语') {
                                                link.click();
                                                return { success: true, action: 'clicked tab/button' };
                                            }
                                        }
                                        
                                        // 尝试模糊匹配
                                        for (const link of links) {
                                            const txt = link.textContent.trim();
                                            if (txt.includes('自己设置') && txt.includes('招呼语')) {
                                                link.click();
                                                return { success: true, action: 'clicked fuzzy match' };
                                            }
                                        }
                                        
                                        return { success: false, action: 'not found' };
                                    }""")
                                    
                                    if switch_result.get('success'):
                                        print(f"   ✅ 切换到'自己设置招呼语'成功")
                                        page.wait_for_timeout(1000)
                                    else:
                                        print(f"   ℹ️ 未找到单独的自己设置招呼语选项，可能已经在该页面")
                                        
                                except Exception as e:
                                    print(f"   ⚠️ 切换招呼语类型异常: {e}")
                                
                                # 填写招呼语 - 根据职位生成招呼语
                                job_title_for_greeting = matched_job.get('jobTitle', '') if matched_job else ''
                                greeting_msg = generate_greeting_message(job_title_for_greeting)
                                print(f"   [UI] 生成的招呼语: {greeting_msg}")
                                try:
                                    # 使用JavaScript查找并填写招呼语
                                    js_fill_result = page.evaluate("""(greeting) => {
                                        // 查找招呼语输入框 - 可能是textarea或input
                                        const inputs = document.querySelectorAll('textarea, input');
                                        for (const inp of inputs) {
                                            const placeholder = inp.placeholder || '';
                                            const className = inp.className || '';
                                            const tagName = inp.tagName.toLowerCase();
                                            
                                            // 匹配招呼语相关的输入框
                                            if (tagName === 'textarea' || 
                                                placeholder.includes('招呼') || 
                                                placeholder.includes('message') ||
                                                placeholder.includes('模板') ||
                                                className.includes('greet') ||
                                                className.includes('message')) {
                                                
                                                // 填写默认招呼语
                                                inp.value = greeting;
                                                // 触发input和change事件
                                                inp.dispatchEvent(new Event('input', { bubbles: true }));
                                                inp.dispatchEvent(new Event('change', { bubbles: true }));
                                                return { success: true, placeholder: placeholder };
                                            }
                                        }
                                        return { success: false, error: '未找到招呼语输入框' };
                                    }""", greeting_msg)
                                    
                                    if js_fill_result.get('success'):
                                        print(f"   ✅ 填写招呼语成功: {js_fill_result.get('placeholder')}")
                                    else:
                                        print(f"   ⚠️ 填写招呼语失败: {js_fill_result.get('error')}")
                                        
                                except Exception as e:
                                    print(f"   ⚠️ 填写招呼语异常: {e}")
                                
                                page.wait_for_timeout(500)
                                
                                # 点击"使用并发送"按钮
                                print("   [UI] 点击'使用并发送'按钮...")
                                try:
                                    # 使用JavaScript查找并点击按钮
                                    js_click_result = page.evaluate("""() => {
                                        const buttons = document.querySelectorAll('button');
                                        for (const btn of buttons) {
                                            const txt = btn.textContent.trim();
                                            if (txt.includes('使用并发送') || txt.includes('发送')) {
                                                btn.click();
                                                return { success: true, text: txt };
                                            }
                                        }
                                        return { success: false, error: '未找到使用并发送按钮' };
                                    }""")
                                    
                                    if js_click_result.get('success'):
                                        print(f"   ✅ 点击'使用并发送'成功: {js_click_result.get('text')}")
                                        page.wait_for_timeout(2000)
                                        target_found = True
                                    else:
                                        print(f"   ⚠️ 点击'使用并发送'失败: {js_click_result.get('error')}")
                                        
                                except Exception as e:
                                    print(f"   ⚠️ 点击'使用并发送'异常: {e}")
                            else:
                                print(f"   ℹ️ 未检测到AI招呼语对话框（旧版流程直接发送成功）")
                                target_found = True
                        else:
                            print(f"   ⚠️ JavaScript点击失败: {js_result.get('error')}")
                            
                    except Exception as e:
                        print(f"   ⚠️ 点击确定失败: {e}")
                    
                    page.wait_for_timeout(1000)
                    if screenshot:
                        page.screenshot(path=f"{debug_dir}/greet_06_after_confirm.png")
                else:
                    print(f"   ⚠️ 选择岗位失败: {select_result.get('error')}")
                    if select_result.get('samples'):
                        print(f"   选项示例: {select_result.get('samples')}")
                    if screenshot:
                        page.screenshot(path=f"{debug_dir}/greet_07_select_failed.png")
            
            browser.close()
            
            if target_found and greet_button_clicked:
                print(f"\n✅ 成功向 {candidate_name} 发送打招呼消息!")
                return True
            else:
                print(f"\n❌ 打招呼失败")
                return None
            
    except Exception as e:
        print(f"打招呼过程出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description='智联招聘主动打招呼脚本（改造版）')
    parser.add_argument('--name', '-n', required=True, help='候选人姓名')
    parser.add_argument('--index', '-i', type=int, default=None, help='候选人序号（1-based，对应初筛报告中的序号；提供后将优先按序号定向联系）')
    parser.add_argument('--keyword', '-k', help='搜索关键词（岗位名称，不填则从上次搜索上下文读取）')
    parser.add_argument('--location', '-l', help='工作地点（如"河南-周口"）')
    parser.add_argument('--education', '-e', help='学历要求（如"本科"）')
    parser.add_argument('--experience', '-exp', help='工作经验要求（如"1-3年"）')
    parser.add_argument('--cookies', help='Cookie字符串（可选）')
    parser.add_argument('--screenshot', '-s', action='store_true', help='每步操作后截图调试')
    parser.add_argument('--job-select', default='auto', help='职位选择模式：auto=自动匹配，first=选择第一个')
    
    args = parser.parse_args()
    
    # 候选人信息，用于更精确匹配
    candidate_info = None
    context = None
    
    # 尝试从上次搜索上下文加载（包含候选人信息和搜索参数）
    context = load_search_context()
    if context is not None:
        print(f"\n   从上下文加载候选人信息...")
        candidates = context.get('candidates', [])
        
        # 增强：按序号定向（优先级最高）
        # 当用户说"联系序号4李先生"时，先用序号定位候选人，再用多字段校验
        if args.index is not None and candidates:
            if 1 <= args.index <= len(candidates):
                c = candidates[args.index - 1]  # 转为0-based
                candidate_info = {
                    'name': c.get('name', ''),
                    'age': c.get('age', ''),
                    'work_years': c.get('work_years', ''),
                    'education': c.get('education', ''),
                    'resume_number': c.get('resume_number', '')
                }
                actual_name = c.get('name', '')
                args.name = actual_name
                print(f"   [序号定向] 序号{args.index} → {actual_name}")
                print(f"   [序号定向] 完整候选人信息: {candidate_info}")
            else:
                print(f"   [序号定向] 错误：序号{args.index}超出范围（1-{len(candidates)}）")
        elif candidates:
            # 原逻辑：按姓名查找匹配的候选人
            for c in candidates:
                cname = c.get('name', '')
                if cname == args.name or cname.replace('先生', '').replace('女士', '') == args.name.replace('先生', '').replace('女士', ''):
                    candidate_info = {
                        'name': c.get('name', ''),
                        'age': c.get('age', ''),
                        'work_years': c.get('work_years', ''),
                        'education': c.get('education', ''),
                        'resume_number': c.get('resume_number', '')
                    }
                    print(f"   已加载候选人信息: {candidate_info}")
                    break
    
    # 从上下文加载搜索参数（keyword、location、education、experience）
    # 优先使用命令行参数，命令行未提供时自动从上下文补充
    if context:
        if not args.keyword:
            args.keyword = context.get('keywords', '')
        if not args.location:
            args.location = context.get('location', '')
        if not args.education:
            args.education = context.get('education', '')
        if not args.experience:
            args.experience = context.get('experience', '')
    
    # 如果没有任何关键词，返回错误
    if not args.keyword:
        print("错误：请提供搜索关键词或先运行简历搜索")
        return 1
    
    cookies = args.cookies
    if not cookies:
        cookies = load_cookies()
        if not cookies:
            print("错误：请提供Cookie")
            return 1
    
    result = greet_candidate(
        args.name, 
        args.keyword, 
        cookies=cookies,
        location=args.location,
        education=args.education,
        experience=args.experience,
        screenshot=args.screenshot,
        candidate_info=candidate_info
    )
    
    if result:
        print("\n✅ 打招呼完成!")
        return 0
    else:
        print("\n❌ 打招呼失败，请检查日志")
        return 1


if __name__ == '__main__':
    sys.exit(main())
