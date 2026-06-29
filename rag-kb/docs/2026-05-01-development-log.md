# 智联招聘简历助手 (zhaopin-skill) 开发记录

## 2026年5月1日开发记录

### 日期：2026-05-01

### 主要工作内容

#### 1. 技能初始化与测试
- 使用 skill-creator 初始化技能 `zhaopin-resume-scraper`
- 技能路径：`~/.openclaw/workspace-hr/skills/zhaopin-resume-scraper/`
- 创建了完整的技能结构：SKILL.md、脚本、API参考文档

#### 2. Cookie 配置
- 用户提供了最新的 Cookie 值
- Cookie 已配置到请求头中
- 技能文件已重新打包

#### 3. 测试 "Agent工程师" 岗位
- 抓取参数：
  - 简历数量：5份
  - 岗位名称：Agent工程师
  - 工作地点：河南周口
  - 学历要求：本科及以上
  - 工作经验：不限

#### 4. 发现的问题

**问题描述：**
抓取的简历数据与搜索的岗位结果不一致

**具体表现：**
- 简历中多个字段显示为"未知"
- 姓名显示为"未知"
- 学历、教育经历显示为"未知"
- 薪资显示为"未知"
- 工作经历为空

**原因分析：**
- API 返回的数据结构与脚本预期的字段名不匹配
- 脚本中使用的字段名与实际 API 响应字段不一致
- 模板替换逻辑存在问题，导致旧数据残留在报告中

**API 响应字段（实际）：**
```json
{
  "userName": "闫先生",
  "gender": "男",
  "age": "27",
  "workYears": "8",
  "educationLevel": "",
  "careerStatus": "离职-正在找工作",
  "desiredCity": "周口",
  "desiredJobType": "Java",
  "desiredSalary": "1万-1.3万"
}
```

**脚本预期字段（错误）：**
```json
{
  "name": "闫先生",       // 实际是 userName
  "gender": "男",         // 正确
  "age": "27",            // 实际是字符串 "27"
  "workYears": "8",       // 实际是 workYears
  "education": "",         // 实际是 educationLevel
  "jobStatus": "",        // 实际是 careerStatus
  "expectedCity": "",      // 实际是 desiredCity
  "expectedPosition": "",   // 实际是 desiredJobType
  "expectedSalary": ""     // 实际是 desiredSalary
}
```

### 关键修复记录

#### 修复字段映射
| 正确字段名 | 脚本中的错误字段名 |
|------------|-------------------|
| userName | name |
| educationLevel | education |
| careerStatus | jobStatus |
| desiredCity | expectedCity |
| desiredJobType | expectedPosition |
| desiredSalary | expectedSalary |
| workExperiences | workExperience |
| educationExperiences | educationExperience |
| skillTags / displayTags | skillTags |

### 技术要点

#### 1. 城市 ID 映射
| 城市 | ID |
|------|-----|
| 周口 | 734 |
| 郑州 | 719 |
| 北京 | 530 |

#### 2. 学历 ID 映射
| 学历 | ID |
|------|-----|
| 大专 | 3 |
| 本科 | 4 |
| 硕士 | 10 |
| 博士 | 1 |

#### 3. API 接口
- 搜索接口：`POST https://rd6.zhaopin.com/api/talent/search/list`
- 详情接口：`POST https://rd6.zhaopin.com/api/resume/detail`

### 后续优化方向（待完成）

1. **字段映射修复** - 修正脚本中的字段名与 API 响应匹配
2. **模板清理** - 确保模板替换完整，不残留旧数据
3. **错误处理** - 添加更完善的错误处理和日志
4. **数据验证** - 添加 API 响应数据验证逻辑

### 相关文件路径

- 技能目录：`/root/.openclaw/workspace-hr/skills/zhaopin-resume-scraper/`
- 技能文件：`/root/.openclaw/workspace-hr/skills/zhaopin-resume-scraper.skill`
- 报告目录：`/lhcos-datas/reports/初筛报告/`、`/lhcos-datas/reports/详细报告/`
- Cookie 配置：`/root/.openclaw/workspace-hr/config/zhaopin_cookies.txt`

---

## 重要发现

### API 数据结构关键字段

**搜索结果 (list 数组中的对象)：**
- `userName`: 候选人姓名
- `gender`: 性别
- `age`: 年龄（字符串）
- `workYearsLabel`: 工作年限标签
- `educationLevel`: 最高学历
- `careerStatus`: 求职状态
- `desiredCity`: 期望城市
- `desiredJobType`: 期望职位
- `desiredSalary`: 期望薪资
- `newUserActiveTag.describe`: 活跃状态描述
- `workExperiences`: 工作经历数组
  - `companyName`: 公司名称
  - `jobTitle`: 职位名称
  - `beginDate` / `endDate`: 开始/结束时间
  - `duration`: 工作时长
- `educationExperiences`: 教育经历数组
  - `schoolName`: 学校名称
  - `majorName`: 专业名称
  - `educationLevel`: 学历
- `displayTags`: 技能标签数组
  - `name`: 标签名称
- `resumeNumber`: 简历编号（获取详情用）
- `resumeK`: 简历加密 key
- `isSchoolResume`: 是否为校园简历
