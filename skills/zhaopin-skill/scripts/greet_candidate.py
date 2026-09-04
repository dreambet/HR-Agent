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


def get_city_ids(city_name):
    """城市名转ID列表，支持多城市复合地点（如 周口-深圳-东莞）。
    全部城市都无法识别时回退到默认 734（周口），与 get_city_id 行为一致，避免空列表。"""
    if not city_name:
        return []
    city_map = {
        "周口": 734, "郑州": 701, "北京": 530, "上海": 538,
        "深圳": 765, "广州": 763, "杭州": 653, "南京": 635,
        "东莞": 779, "中山": 780, "成都": 801, "武汉": 736,
        "西安": 854, "长沙": 749, "重庆": 551, "苏州": 639,
        "宝安": 765, "惠州": 773, "清溪": 779,
    }
    ids = []
    for part in city_name.replace(' ', '-').split('-'):
        part = part.strip()
        if not part:
            continue
        # 处理 "河南-周口" 格式，取最后一段
        pid = city_map.get(part)
        if pid is not None and pid not in ids:
            ids.append(pid)
    # 兜底：全部无法识别时回退默认周口，避免空数组导致API异常
    if not ids:
        ids = [734]
    return ids


def build_filter_params(location=None, education=None, experience=None):
    """构建过滤参数（尽量与search_resumes.py一致，支持多城市）"""
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
        city_ids = get_city_ids(location)
        if city_ids:
            params['expectedCityIds'] = city_ids
    
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


def _find_modal_for_candidate(page, candidate_name):
    """返回包含候选人姓名的‘选择沟通职位’弹窗（Playwright Locator），找不到返回 None
    支持多个弹窗叠加时按姓名精确锁定。"""
    # 优先：可见的 .km-modal__wrapper
    for sel in ['.km-modal__wrapper:visible', '.resume-buttons-chat', '.km-modal__wrapper']:
        modals = page.locator(sel)
        for i in range(modals.count()):
            m = modals.nth(i)
            try:
                txt = m.inner_text() or ''
            except Exception:
                continue
            if '选择沟通职位' in txt and candidate_name in txt:
                return m
    # 兜底：任意 dialog/modal 含候选人名
    try:
        modals = page.locator('[role="dialog"], .km-modal, .s-dialog')
        for i in range(modals.count()):
            m = modals.nth(i)
            try:
                txt = m.inner_text() or ''
            except Exception:
                continue
            if '选择沟通职位' in txt and candidate_name in txt:
                return m
    except Exception:
        pass
    return None


def _click_in_modal(page, modal, texts):
    """在指定 modal 内点击文本匹配的按钮；返回 (是否成功, 按钮文本)"""
    try:
        btns = modal.locator('button:visible')
        for i in range(btns.count()):
            try:
                t = (btns.nth(i).text_content() or '').strip()
            except Exception:
                continue
            if t in texts or any(x in t for x in texts):
                btns.nth(i).click(force=True)
                return True, t
    except Exception:
        pass
    return False, None


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


def send_greeting_robust(page, candidate_name, job_title, job_number, screenshot=False, debug_dir=''):
    """
    健壮版打招呼发送：按候选人姓名精确锁定弹窗，逐步处理关键词框→选职位→确定→使用并发送→验证。
    返回：True=确认成功, False=确认失败, None=无法确定(需人工复核)
    """
    import json as _json
    page.wait_for_timeout(1500)

    # ---- 强制关闭“请选择关键词”对话框（若存在）：直接点它自己的“确定”----
    for _attempt in range(3):
        kw_dialog = page.evaluate('''() => {
            const ds = document.querySelectorAll('.s-dialog');
            for (const d of ds) {
                const t = (d.innerText || '');
                const st = window.getComputedStyle(d);
                const r = d.getBoundingClientRect();
                if (st.display === 'none' || st.visibility === 'hidden' || (r.width === 0 && r.height === 0)) continue;
                if (t.includes('请选择关键词')) return { found: true };
            }
            return { found: false };
        }''')
        if not kw_dialog.get('found'):
            break
        print(f"   [健壮] 发现残留关键词选择框，直接点确定关闭...")
        closed = page.evaluate('''() => {
            const ds = document.querySelectorAll('.s-dialog');
            for (const d of ds) {
                const t = (d.innerText || '');
                const st = window.getComputedStyle(d);
                const r = d.getBoundingClientRect();
                if (st.display === 'none' || st.visibility === 'hidden' || (r.width === 0 && r.height === 0)) continue;
                if (!t.includes('请选择关键词')) continue;
                const btns = d.querySelectorAll('button');
                for (const b of btns) {
                    const bt = (b.textContent || '').trim();
                    if (bt === '确定' || bt === '确 定') { b.click(); return true; }
                }
                // 若无确定按钮，点关闭图标
                const close = d.querySelector('[class*="close"]');
                if (close) { close.click(); return true; }
            }
            return false;
        }''')
        print(f"   [健壮] 关键词框关闭操作: {closed}")
        page.wait_for_timeout(1500)

    # ---- 定位包含候选人姓名的“选择沟通职位”弹窗 ----
    modal = _find_modal_for_candidate(page, candidate_name)
    if modal is None:
        print(f"   [健壮] ❌ 未找到 {candidate_name} 的沟通职位弹窗")
        return False
    print(f"   [健壮] ✅ 已定位 {candidate_name} 的沟通职位弹窗")
    if screenshot:
        page.screenshot(path=f"{debug_dir}/r1_modal_found.png")

    # ---- 选择沟通职位 ----
    # 先看职位是否已选
    pos_state = page.evaluate('''() => {
        const modals = [...document.querySelectorAll('.km-modal__wrapper')].filter(m => {
            const st = window.getComputedStyle(m); const r = m.getBoundingClientRect();
            return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        });
        const target = [...modals].find(m => (m.innerText||'').includes('选择沟通职位') && (m.innerText||'').includes('候选人'));
        if (!target) return { hasModal: false };
        const inputs = target.querySelectorAll('input');
        for (const inp of inputs) {
            if ((inp.placeholder||'').includes('沟通职位')) {
                return { hasModal: true, value: (inp.value||'').trim() };
            }
        }
        return { hasModal: true, value: '' };
    }''')
    print(f"   [健壮] 职位当前值: {pos_state.get('value') or '(空)'}")

    if not pos_state.get('value'):
        # 打开下拉
        page.evaluate('''() => {
            const modals = [...document.querySelectorAll('.km-modal__wrapper')].filter(m => {
                const st = window.getComputedStyle(m); const r = m.getBoundingClientRect();
                return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
            });
            const target = [...modals].find(m => (m.innerText||'').includes('选择沟通职位') && (m.innerText||'').includes('候选人'));
            if (!target) return;
            const inputs = target.querySelectorAll('input');
            for (const inp of inputs) {
                if ((inp.placeholder||'').includes('沟通职位')) { inp.click(); break; }
            }
        }''')
        page.wait_for_timeout(1200)
        try:
            page.wait_for_selector('.km-select__dropdown', timeout=4000)
            print(f"   [健壮] 下拉已打开")
        except Exception:
            print(f"   [健壮] ⚠️ 下拉未出现，继续尝试")
        # 搜索职位并选择
        page.wait_for_timeout(800)
        # 带参数版本：在下拉搜索框输入职位
        sel = page.evaluate("""(jobTitle) => {
            const drops = document.querySelectorAll('.km-select__dropdown');
            const drop = [...drops].find(d => { const st = window.getComputedStyle(d); return st.display !== 'none' && st.visibility !== 'hidden'; });
            if (!drop) return { ok: false, err: 'no dropdown' };
            const search = drop.querySelector('input');
            if (search) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(search, jobTitle);
                search.dispatchEvent(new Event('input', { bubbles: true }));
                search.dispatchEvent(new Event('change', { bubbles: true }));
            }
            return { ok: true };
        }""", job_title)
        print(f"   [健壮] 下拉搜索输入: {sel}")
        page.wait_for_timeout(1200)
        # 选择匹配选项：优先点击选项的可点子元素（title/label），确保框架识别
        opt = page.evaluate("""(jobTitle) => {
            const drops = document.querySelectorAll('.km-select__dropdown');
            const drop = [...drops].find(d => { const st = window.getComputedStyle(d); return st.display !== 'none' && st.visibility !== 'hidden'; });
            if (!drop) return { ok: false, err: 'no dropdown' };
            // 候选：选项容器本身、其下的 title/label/可点元素
            const containers = drop.querySelectorAll('.jsn-job-selector__option--container, [class*="option"], li');
            const clickTargets = (el) => {
                const t = (el.textContent || '').trim();
                return { el, t, clickable: el.querySelector('title, label, [class*="title"], [class*="label"], span, p') };
            };
            for (const c of containers) {
                const t = (c.textContent || '').trim();
                if (t && (t === jobTitle || t.includes(jobTitle) || jobTitle.includes(t))) {
                    // 点击选项（优先子元素）
                    const child = c.querySelector('.jsn-job-selector__option--title, [class*="title"], label, span');
                    (child || c).click();
                    // 触发 mousedown/click 序列（部分框架需要）
                    c.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    c.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                    c.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    return { ok: true, text: t };
                }
            }
            // 无精确匹配：选第一个可点选项
            for (const c of containers) {
                const t = (c.textContent || '').trim();
                if (t && !t.includes('请选择')) {
                    const child = c.querySelector('.jsn-job-selector__option--title, [class*="title"], label, span');
                    (child || c).click();
                    c.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    c.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    return { ok: true, text: t, fallback: true };
                }
            }
            return { ok: false, err: 'no options' };
        }""", job_title)
        print(f"   [健壮] 选项选择: {opt}")
        page.wait_for_timeout(1500)
        # 验证职位是否已填入输入框（不强制隐藏下拉，让框架正常提交）
        pos_check = page.evaluate('''() => {
            const modals = [...document.querySelectorAll('.km-modal__wrapper')].filter(m => {
                const st = window.getComputedStyle(m); const r = m.getBoundingClientRect();
                return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
            });
            const target = [...modals].find(m => (m.innerText||'').includes('选择沟通职位') && (m.innerText||'').includes('候选人'));
            if (!target) return { filled: false, err: 'no modal' };
            const inputs = target.querySelectorAll('input');
            for (const inp of inputs) {
                if ((inp.placeholder||'').includes('沟通职位')) return { filled: !!((inp.value||'').trim()), value: (inp.value||'').trim() };
            }
            return { filled: false, err: 'no input' };
        }''')
        print(f"   [健壮] 职位填入验证: {pos_check}")
        if not pos_check.get('filled'):
            print(f"   [健壮] ⚠️ 职位未填入输入框，尝试 Playwright 原生点击最后一个匹配选项")
            try:
                # 用 Playwright 直接点下拉里匹配的选项
                drops = page.locator('.km-select__dropdown:visible')
                if drops.count() > 0:
                    opts = drops.first.locator('.jsn-job-selector__option--container, [class*="option"]')
                    for i in range(opts.count()):
                        try:
                            t = (opts.nth(i).text_content() or '').strip()
                        except Exception:
                            continue
                        if t and (job_title in t or t in job_title):
                            opts.nth(i).click(force=True)
                            print(f"   [健壮] Playwright 点击选项: {t[:30]}")
                            break
                page.wait_for_timeout(1200)
            except Exception as _pe:
                print(f"   [健壮] Playwright 点选项失败: {_pe}")

    # ---- 在候选人弹窗内点确定 ----
    modal2 = _find_modal_for_candidate(page, candidate_name)
    if modal2 is None:
        print(f"   [健壮] ❌ 沟通职位弹窗消失（可能已提交或出错）")
        return None
    ok_click, btn_txt = _click_in_modal(page, modal2, ['确定', '确 定', '确认'])
    if ok_click:
        print(f"   [健壮] ✅ 点击确定「{btn_txt}」")
    else:
        print(f"   [健壮] ⚠️ 未找到确定按钮，尝试 JS 兜底")
        page.evaluate('''() => {
            const modals = [...document.querySelectorAll('.km-modal__wrapper')].filter(m => {
                const st = window.getComputedStyle(m); const r = m.getBoundingClientRect();
                return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
            });
            for (const m of modals) {
                if (!(m.innerText||'').includes('选择沟通职位')) continue;
                const btns = m.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent||'').trim();
                    if (t === '确定' || t === '确 定') { b.click(); return; }
                }
            }
        }''')
    page.wait_for_timeout(2500)
    if screenshot:
        page.screenshot(path=f"{debug_dir}/r2_after_confirm.png")

    # ---- 诊断：dump 确定后所有可见弹窗（找 AI 招呼语框）----
    _modals_after = page.evaluate('''() => {
        const out = [];
        document.querySelectorAll('.km-modal__wrapper, .s-dialog, [role="dialog"], [class*="modal"]').forEach(m => {
            const st = window.getComputedStyle(m); const r = m.getBoundingClientRect();
            if (st.display === 'none' || st.visibility === 'hidden' || r.width === 0 || r.height === 0) return;
            const btns = [];
            m.querySelectorAll('button').forEach(b => {
                const bs = window.getComputedStyle(b);
                if (bs.display !== 'none' && bs.visibility !== 'hidden') btns.push((b.textContent||'').trim().slice(0,30));
            });
            const inputs = [];
            m.querySelectorAll('input, textarea').forEach(i => {
                inputs.push({ph: (i.placeholder||'').slice(0,20), val: (i.value||'').toString().slice(0,30)});
            });
            out.push({cls: (m.className||'').toString().slice(0,60), text: (m.innerText||'').trim().replace(/\s+/g,' ').slice(0,250), btns, inputs});
        });
        return out;
    }''')
    print(f"   [健壮] 确定后可见弹窗数={len(_modals_after)}")
    for _i, _mm in enumerate(_modals_after):
        print(f"     [{_i}] cls={_mm['cls']} btns={_mm['btns']} inputs={[ (x['ph'],x['val']) for x in _mm['inputs'] ]}")
        print(f"          text={_mm['text'][:200]}")

    # ---- 监听发送 API ----
    send_hits = []
    def _on_resp(resp):
        try:
            u = resp.url.lower()
            if any(k in u for k in ['greet', 'sendtext', 'im/send', 'im/sendtext', 'invite', 'message/send']):
                send_hits.append({'status': resp.status, 'url': resp.url[:130]})
        except Exception:
            pass
    page.on('response', _on_resp)

    # ---- 点击“使用并发送”或“发送” ----
    send_clicked = False
    # 先检查候选人的弹窗是否还有按钮
    modal3 = _find_modal_for_candidate(page, candidate_name)
    if modal3 is not None:
        ok3, txt3 = _click_in_modal(page, modal3, ['使用并发送', '发送'])
        if ok3:
            send_clicked = True
            print(f"   [健壮] ✅ 点击「{txt3}」")
    if not send_clicked:
        # 全局查找（但排除无关弹窗）
        btns = page.locator('button:visible')
        for i in range(btns.count()):
            try:
                t = (btns.nth(i).text_content() or '').strip()
            except Exception:
                continue
            if '使用并发送' in t or t == '发送':
                btns.nth(i).click(force=True)
                send_clicked = True
                print(f"   [健壮] ✅ 点击全局「{t}」")
                break
    if not send_clicked:
        print(f"   [健壮] ❌ 未找到发送按钮")
    page.wait_for_timeout(3500)
    if screenshot:
        page.screenshot(path=f"{debug_dir}/r3_after_send.png")

    # ---- 验证是否真实发送 ----
    page_warn = page.evaluate('''() => {
        const body = document.body.innerText || '';
        return ['\u804a\u5929\u6743\u76ca','\u641c\u804a\u52a0\u6cb9\u5305','\u6b21\u6570\u5df2\u7528\u5b8c','\u4f59\u989d\u4e0d\u8db3','\u53d1\u9001\u5931\u8d25'].filter(k => body.includes(k));
    }''')
    remaining = page.evaluate('''() => {
        let n = 0;
        [...document.querySelectorAll('.km-modal__wrapper')].forEach(m => {
            const st = window.getComputedStyle(m); const r = m.getBoundingClientRect();
            if (st.display === 'none' || st.visibility === 'hidden' || r.width === 0 || r.height === 0) return;
            const t = m.innerText || '';
            if (t.includes('选择沟通职位') || t.includes('请选择关键词')) n++;
        });
        return n;
    }''')
    ok_api = any(h.get('status') and 200 <= int(h['status']) < 300 for h in send_hits)
    print(f"   [健壮] 验证: 发送API={len(send_hits)}条 ok={ok_api} | 剩余相关弹窗={remaining} | 告警={page_warn}")

    if page_warn:
        print(f"   [健壮] ❌ 检测到权益/失败告警: {page_warn}")
        return False
    if ok_api:
        print(f"   [健壮] ✅ 捕获到发送API，确认成功")
        return True
    if remaining == 0:
        print(f"   [健壮] ⚠️ 未捕获API但弹窗已关闭，判定可能成功（弱证据，请人工复核）")
        return None
    print(f"   [健壮] ❌ 无发送API且弹窗仍存在({remaining}个)，判定失败")
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
                        # 使用Playwright点击，避免JS click假成功
                        send_btn = None
                        visible_btns = page.locator('button:visible').all()
                        for btn in visible_btns:
                            try:
                                txt = btn.text_content().strip()
                                if '使用并发送' in txt or txt == '发送':
                                    send_btn = btn
                                    break
                            except:
                                continue
                        
                        if send_btn:
                            try:
                                send_btn.click(force=True)
                                print(f"   ✅ Playwright 点击'使用并发送'成功")
                            except Exception as e:
                                print(f"   ⚠️ Playwright点击失败，尝试坐标点击: {e}")
                                box = send_btn.bounding_box()
                                if box:
                                    page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                    print(f"   ✅ 坐标点击'使用并发送'成功")
                            
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
                                print(f"   ⚠️ 对话框仍存在({remaining}个)，可能未成功发送")
                        else:
                            print(f"   ⚠️ 未找到'使用并发送'按钮")
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
                    
                    # 点击确定按钮（使用Playwright click，避免JS click假成功）
                    print(f"   点击确定按钮...")
                    confirm_btn = None
                    visible_btns = page.locator('button:visible').all()
                    for btn in visible_btns:
                        try:
                            txt = btn.text_content().strip()
                            if txt in ('确定', '确认'):
                                confirm_btn = btn
                                break
                        except:
                            continue
                    
                    if confirm_btn:
                        try:
                            confirm_btn.click(force=True)
                            print(f"   ✅ Playwright 点击确定按钮成功")
                        except Exception as e:
                            print(f"   ⚠️ Playwright点击失败，尝试坐标点击: {e}")
                            try:
                                box = confirm_btn.bounding_box()
                                if box:
                                    page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                    print(f"   ✅ 坐标点击确定按钮成功")
                            except Exception as e2:
                                print(f"   ⚠️ 坐标点击也失败: {e2}")
                    else:
                        print(f"   ⚠️ 未找到确定按钮")
                    
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

                # ==== 健壮版发送（优先）：按候选人锁定弹窗，真实验证发送 ====
                try:
                    _robust_result = send_greeting_robust(
                        page, candidate_name, job_title, job_number,
                        screenshot=screenshot, debug_dir=debug_dir
                    )
                    browser.close()
                    if _robust_result is True:
                        print(f"   ✅ 健壮版发送确认成功")
                        print(f"\n✅ 成功向 {candidate_name} 发送打招呼消息!")
                        return True
                    elif _robust_result is None:
                        print(f"   ⚠️ 健壮版：未捕获发送API但弹窗已关闭，判定可能成功（弱证据，请人工复核）")
                        print(f"\n⚠️ 已向 {candidate_name} 发起打招呼（未确认，请人工复核）")
                        return True
                    else:
                        print(f"   ❌ 健壮版确认发送失败")
                        print(f"\n❌ 打招呼失败")
                        return None
                except Exception as _e:
                    print(f"   ⚠️ 健壮版执行异常，回退旧逻辑: {_e}")
                
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
                    
                    # 先检查职位是否已经被选中
                    current_value = page.evaluate("""() => {
                        const inputs = document.querySelectorAll('input');
                        for (const inp of inputs) {
                            const placeholder = inp.placeholder || '';
                            if (placeholder.includes('沟通职位')) {
                                return inp.value || '';
                            }
                        }
                        return '';
                    }""")
                    print(f"   [UI] 当前职位值: {current_value}")
                    
                    if current_value.strip() and (job_title.strip() in current_value.strip() or current_value.strip() in job_title.strip()):
                        print(f"   ✅ 职位已选中: {current_value}，跳过下拉选择")
                        select_result = {'success': True}
                    else:
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
                                page.wait_for_timeout(800)
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
                                        
                                        if job_title.strip() == option_title.strip():
                                            opt.click()
                                            print(f"   ✅ 精确匹配选中: {option_title}")
                                            selected = True
                                            break
                                        elif job_title.strip() in option_title.strip() or option_title.strip() in job_title.strip():
                                            opt.click()
                                            print(f"   ✅ 部分匹配选中: {option_title}")
                                            selected = True
                                            break
                                except Exception as e:
                                    continue
                            
                            if not selected and len(option_containers) > 0:
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
                        # 使用 Playwright locator 查找并点击确定按钮
                        # 先关闭下拉列表
                        page.evaluate("""() => {
                            const dropdown = document.querySelector('.km-select__dropdown');
                            if (dropdown) dropdown.style.display = 'none';
                        }""")
                        page.wait_for_timeout(500)

                        confirm_btn = None
                        # 方案1: 在模态框中查找（只用精确的 km-modal__wrapper）
                        modals = page.locator('.km-modal__wrapper').all()
                        for modal in modals:
                            try:
                                if not modal.is_visible():
                                    continue
                            except:
                                continue
                            # 只查找可见的确定按钮
                            buttons = modal.locator('button:visible').all()
                            for btn in buttons:
                                try:
                                    txt = btn.text_content().strip()
                                    if txt in ('确定', '确认'):
                                        confirm_btn = btn
                                        break
                                except:
                                    continue
                            if confirm_btn:
                                break

                        # 方案2: 直接用 Playwright 全局查找可见的确定按钮
                        if not confirm_btn:
                            visible_btns = page.locator('button:visible').all()
                            for btn in visible_btns:
                                try:
                                    txt = btn.text_content().strip()
                                    if txt in ('确定', '确认'):
                                        confirm_btn = btn
                                        break
                                except:
                                    continue

                        if confirm_btn:
                            try:
                                confirm_btn.click(force=True)
                                print(f"   ✅ Playwright 点击确定按钮成功")
                                js_result = {'success': True, 'source': 'playwright'}
                            except Exception as e:
                                print(f"   ⚠️ Playwright点击失败: {e}")
                                # 回退: 使用坐标点击
                                try:
                                    box = confirm_btn.bounding_box()
                                    if box:
                                        page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                        print(f"   ✅ 坐标点击确定按钮成功")
                                        js_result = {'success': True, 'source': 'mouse'}
                                    else:
                                        js_result = {'success': False, 'error': '无法获取按钮位置'}
                                except Exception as e2:
                                    js_result = {'success': False, 'error': str(e2)}
                        else:
                            print(f"   ⚠️ 未找到确定按钮")
                            js_result = {'success': False, 'error': '未找到确定按钮'}
                        
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
                                
                                # 直接使用默认AI招呼语，不切换到"自己设置招呼语"
                                # 原因：切换后模态框遮挡导致textarea无法填写，发送空消息
                                print("   [UI] 使用默认AI招呼语，直接发送...")
                                page.wait_for_timeout(500)
                                
                                # 验证职位是否已选中
                                position_value = page.evaluate("""() => {
                                    const inputs = document.querySelectorAll('input');
                                    for (const inp of inputs) {
                                        const placeholder = inp.placeholder || '';
                                        if (placeholder.includes('沟通职位')) {
                                            return inp.value || '';
                                        }
                                    }
                                    return 'NOT_FOUND';
                                }""")
                                print(f"   [验证] 当前沟通职位值: '{position_value}'")
                                if not position_value or position_value == 'NOT_FOUND':
                                    print(f"   ⚠️ 警告：沟通职位可能未选中!")
                                
                                # 监听网络请求，捕获发送招呼语的API调用
                                send_api_results = []
                                def handle_send_response(response):
                                    try:
                                        url = response.url
                                        if 'greet' in url.lower() or 'message' in url.lower() or 'chat' in url.lower() or 'send' in url.lower():
                                            send_api_results.append({
                                                'url': url,
                                                'status': response.status,
                                                'status_text': response.status_text
                                            })
                                    except:
                                        pass
                                
                                page.on('response', handle_send_response)
                                page.wait_for_timeout(500)
                                
                                # 点击"使用并发送"按钮（使用Playwright点击，避免JS click假成功）
                                print("   [UI] 点击'使用并发送'按钮...")
                                try:
                                    send_btn = None
                                    # 方案1: 在模态框中查找可见的发送按钮
                                    modals = page.locator('.km-modal__wrapper').all()
                                    for modal in modals:
                                        try:
                                            if not modal.is_visible():
                                                continue
                                        except:
                                            continue
                                        buttons = modal.locator('button:visible').all()
                                        for btn in buttons:
                                            try:
                                                txt = btn.text_content().strip()
                                                if '使用并发送' in txt or txt == '发送':
                                                    send_btn = btn
                                                    break
                                            except:
                                                continue
                                        if send_btn:
                                            break
                                    
                                    # 方案2: 全局查找可见的发送按钮
                                    if not send_btn:
                                        visible_btns = page.locator('button:visible').all()
                                        for btn in visible_btns:
                                            try:
                                                txt = btn.text_content().strip()
                                                if '使用并发送' in txt or txt == '发送':
                                                    send_btn = btn
                                                    break
                                            except:
                                                continue
                                    
                                    if send_btn:
                                        try:
                                            send_btn.click(force=True)
                                            print(f"   ✅ Playwright 点击'使用并发送'成功")
                                            target_found = True
                                        except Exception as e:
                                            print(f"   ⚠️ Playwright点击失败: {e}")
                                            # 回退: 坐标点击
                                            try:
                                                box = send_btn.bounding_box()
                                                if box:
                                                    page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                                    print(f"   ✅ 坐标点击'使用并发送'成功")
                                                    target_found = True
                                                else:
                                                    print(f"   ⚠️ 无法获取按钮位置")
                                            except Exception as e2:
                                                print(f"   ⚠️ 坐标点击也失败: {e2}")
                                    else:
                                        print(f"   ⚠️ 未找到'使用并发送'按钮")
                                        
                                    page.wait_for_timeout(3000)
                                    
                                    # 检查捕获的网络请求
                                    print(f"   [网络] 捕获到 {len(send_api_results)} 个相关请求:")
                                    for req in send_api_results:
                                        print(f"   [网络]   {req['status']} {req['url'][:100]}")
                                    
                                    # 检查页面上是否有错误提示
                                    error_check = page.evaluate("""() => {
                                        const body = document.body.innerText;
                                        const errors = [];
                                        if (body.includes('失败') || body.includes('error') || body.includes('错误')) {
                                            errors.push('页面包含错误提示');
                                        }
                                        // 检查toast提示
                                        const toasts = document.querySelectorAll('[class*="toast"], [class*="message"], [class*="notification"]');
                                        for (const t of toasts) {
                                            if (t.innerText && t.innerText.trim()) {
                                                errors.push('Toast: ' + t.innerText.trim().substring(0, 100));
                                            }
                                        }
                                        return errors;
                                    }""")
                                    if error_check:
                                        for err in error_check:
                                            print(f"   ⚠️ {err}")
                                    
                                    # 验证对话框是否已关闭（确认发送成功）
                                    remaining_modals = page.evaluate("""() => {
                                        const modals = document.querySelectorAll('.km-modal__wrapper');
                                        let visible = 0;
                                        for (const m of modals) {
                                            const style = window.getComputedStyle(m);
                                            if (style.display !== 'none' && style.visibility !== 'hidden') visible++;
                                        }
                                        return visible;
                                    }""")
                                    if remaining_modals == 0:
                                        print(f"   ✅ 对话框已关闭，发送成功确认")
                                    else:
                                        print(f"   ⚠️ 对话框仍存在({remaining_modals}个)，可能未成功发送")
                                        
                                except Exception as e:
                                    print(f"   ⚠️ 点击'使用并发送'异常: {e}")
                            else:
                                # 修复假成功：不能因为"未检测到AI招呼语对话框"就假定发送成功。
                                # 必须验证实际证据：① 发送类API请求① 或 对话框已关闭且无错误提示
                                print(f"   ℹ️ 未检测到AI招呼语对话框，正在验证是否真实发送...")
                                page.wait_for_timeout(2500)

                                # 证据1：是否有发送类 API 请求成功返回
                                sent_api_ok = False
                                try:
                                    for req in send_api_results:
                                        u = (req.get('url') or '').lower()
                                        st = req.get('status')
                                        if st and 200 <= int(st) < 300 and ('sendtext' in u or 'greet' in u or 'im/send' in u or 'invite' in u):
                                            sent_api_ok = True
                                            print(f"   [验证] 捕获到发送API: {st} {req.get('url')[:100]}")
                                            break
                                except Exception:
                                    pass

                                # 证据2：对话框是否已关闭
                                try:
                                    remaining_modals2 = page.evaluate("""() => {
                                        const modals = document.querySelectorAll('.km-modal__wrapper');
                                        let visible = 0;
                                        for (const m of modals) {
                                            const style = window.getComputedStyle(m);
                                            if (style.display !== 'none' && style.visibility !== 'hidden') visible++;
                                        }
                                        return visible;
                                    }""")
                                except Exception:
                                    remaining_modals2 = -1

                                # 证据3：页面是否有错误/权益不足提示
                                try:
                                    page_warn = page.evaluate("""() => {
                                        const body = document.body.innerText || '';
                                        const hits = [];
                                        ['\u804a\u5929\u6743\u76ca','\u641c\u804a\u52a0\u6cb9\u5305','\u6b21\u6570\u5df2\u7528\u5b8c','\u4f59\u989d\u4e0d\u8db3','\u53d1\u9001\u5931\u8d25'].forEach(k => {
                                            if (body.includes(k)) hits.push(k);
                                        });
                                        return hits;
                                    }""")
                                except Exception:
                                    page_warn = []

                                print(f"   [验证] 发送API命中={sent_api_ok} | 可见对话框={remaining_modals2} | 页面告警={page_warn}")

                                if page_warn:
                                    print(f"   ❌ 页面出现告警（{page_warn}），判定发送失败")
                                    target_found = False
                                elif sent_api_ok:
                                    print(f"   ✅ 已捕获发送API，确认发送成功")
                                    target_found = True
                                elif remaining_modals2 == 0:
                                    print(f"   ⚠️ 未捕获到发送API，但对话框已关闭，判定为可能成功（弱证据，请人工复核）")
                                    target_found = True
                                else:
                                    print(f"   ❌ 无发送API且对话框仍存在（{remaining_modals2}个），判定发送失败")
                                    target_found = False
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
