# 智联招聘API拦截技术文档 (2026-05-11)

## 背景

在自动化获取智联招聘候选人简历时，需要拦截浏览器的API请求以添加过滤条件。

## 问题

Playwright 的 `page.route` 拦截器在某些情况下无法正常工作，注册的路由未被调用。

## 解决方案：JavaScript 层面拦截

在页面加载后，通过 JavaScript 注入的方式拦截 `XMLHttpRequest` 和 `Fetch` API。

### 拦截原理

1. 保存原始的 `XMLHttpRequest.prototype.send` 和 `window.fetch`
2. 用自定义函数替换，当检测到目标 API 请求时：
   - 解析请求 body
   - 添加过滤参数
   - 重新发送请求

### 核心代码

```javascript
(function() {
    const filterParams = {
        expectedCityIds: [734],  // 周口
        educations: ["4"],       // 本科
        workingYears: ["3"]      // 1-3年
    };
    
    // 拦截 XMLHttpRequest
    const originalXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(body) {
        if (this._url && this._url.includes('/api/talent/search/list')) {
            let parsedBody = JSON.parse(body);
            for (const [key, value] of Object.entries(filterParams)) {
                if (!parsedBody[key]) {
                    parsedBody[key] = value;
                }
            }
            body = JSON.stringify(parsedBody);
        }
        return originalXHRSend.call(this, body);
    };
    
    // 拦截 Fetch
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        if (typeof url === 'string' && url.includes('/api/talent/search/list')) {
            if (options && options.body) {
                let body = JSON.parse(options.body);
                for (const [key, value] of Object.entries(filterParams)) {
                    if (!body[key]) {
                        body[key] = value;
                    }
                }
                options.body = JSON.stringify(body);
            }
        }
        return originalFetch.apply(this, arguments);
    };
})();
```

## 智联招聘 API 接口

### 1. 搜索 API

- **URL**: `POST https://rd6.zhaopin.com/api/talent/search/list`
- **作用**: 搜索候选人列表
- **过滤参数**:
  - `expectedCityIds`: 城市ID数组，如 [734] 表示周口
  - `educations`: 学历代码数组，如 ["4"] 表示本科
  - `workingYears`: 经验代码数组，如 ["3"] 表示 1-3年

### 2. 详情 API

- **URL**: `POST https://rd6.zhaopin.com/api/resume/detail`
- **作用**: 获取候选人详细简历
- **参数**: 
  - `resumeNumber`: 简历编号
  - `k`: 加密key（自动生成）
  - `t`: 时间戳（自动生成）
  - `resumeLanguage`: "1"

### 城市ID映射

```python
CITY_MAP = {
    "周口": 734,
    "郑州": 701,
    "北京": 530,
    "上海": 538,
    "深圳": 765,
    "广州": 703,
    "杭州": 653,
    "南京": 653,
}
```

### 学历代码映射

```python
EDU_MAP = {
    "大专": "3",
    "本科": "4",
    "硕士": "10",
    "博士": "5",
}
```

### 经验代码映射

```python
EXP_MAP = {
    "1年以下": "2",
    "1-3年": "3",
    "3-5年": "4",
    "5-10年": "5",
    "10年以上": "6",
}
```

## 与 page.route 的对比

| 特性 | JavaScript拦截 | page.route |
|------|----------------|------------|
| 拦截层级 | 应用层 | Playwright层 |
| XHR拦截 | ✅ 支持 | ❌ 可能失效 |
| Fetch拦截 | ✅ 支持 | ✅ 支持 |
| 稳定性 | 高 | 依赖Playwright版本 |
| 代码复杂度 | 较高 | 较低 |

## 使用场景

当 `page.route` 无法正常拦截请求时，使用 JavaScript 层面的拦截作为替代方案。

特别适用于：
- 智联招聘等使用 XHR 发送请求的网站
- 需要动态修改请求 body 的场景
- 浏览器自动化测试中的请求模拟
