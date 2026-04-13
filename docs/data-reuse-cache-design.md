# 事件驱动投资图谱的数据复用与缓存设计

## 1. 背景

当前项目的主流程是：

1. 输入公司名称 / Ticker + 时间范围
2. 抓取 SEC、Google News、Benzinga 等数据源
3. 过滤文章
4. 抽取事件
5. 聚类事件
6. 生成摘要与关系
7. 组装图谱返回前端

这条链路可以跑通，但存在一个明显问题：

- 每次请求都会重新拉取数据源
- 每次请求都会重新做文章解析和事件抽取
- AI 模式下还会重复做高成本摘要

对于热门公司，这里面大量中间结果其实是可复用的。

因此，系统应从“任务结果持久化”升级为“分层缓存 + 增量复用”。

## 2. 当前实现现状

当前仓库已经具备一部分持久化能力：

- [backend/app/services/storage.py](/Users/bytedance/company-news-graph/backend/app/services/storage.py)
- [backend/app/api/routes.py](/Users/bytedance/company-news-graph/backend/app/api/routes.py)

现状特点：

- 会把单次任务的最终 `task + graph` 存到 `backend/data/tasks/*.json`
- 重启后可以恢复历史任务
- 但新请求依然会重新执行 `run_news_research()`

也就是说，当前存的是“结果快照”，不是“可复用中间层”。

## 3. 设计目标

本设计的目标不是一次性引入复杂数据平台，而是在当前项目上补齐最有价值的复用层。

目标如下：

- 相同查询优先直接复用已有结果
- 时间范围重叠时，尽量复用历史文章与抽取结果
- 避免重复调用外部新闻源
- 避免重复执行 AI 摘要
- 为后续“市场反应层”“事件驱动图谱”“GraphRAG”保留中间结构

非目标：

- 当前阶段不引入图数据库
- 当前阶段不做复杂分布式缓存
- 当前阶段不追求强一致实时同步

## 4. 分层缓存思路

建议把缓存拆成 5 层，而不是只缓存最终图谱。

### 4.1 Layer A: 查询结果层

作用：

- 对完全相同的研究请求直接返回已有结果

缓存对象：

- 最终 `GraphResponse`
- 对应 `TaskStatusResponse`

适用场景：

- 同一个公司 / ticker
- 相同时间范围
- 相同 `report_mode`
- 相同 schema / prompt 版本

这是命中成本最低、用户感知最强的一层。

### 4.2 Layer B: 原始数据源层

作用：

- 缓存各个外部数据源返回的文章列表，避免重复抓取

缓存对象：

- Google News RSS 结果
- SEC EDGAR filings 结果
- Benzinga 结果
- 未来可扩展的 Reuters / IR / transcript 结果

这层缓存的是“抓回来的原始结果”，保留源站字段。

### 4.3 Layer C: 标准化文章层

作用：

- 将不同数据源的文章统一为内部 `NewsArticle` 结构
- 去重后形成稳定文章主表

缓存对象：

- 标准化后的文章对象
- 文章唯一标识
- 抓取时间
- 来源类型

这一层是后续事件抽取和证据复用的关键基础。

### 4.4 Layer D: 文章级抽取层

作用：

- 复用对单篇文章的结构化理解结果

缓存对象：

- `event_type`
- `event_label`
- `summary`
- 初步实体抽取结果
- 文章级关系抽取结果

这层最适合承接规则抽取和未来的 LLM 抽取。

### 4.5 Layer E: 事件簇摘要层

作用：

- 对已聚类事件生成摘要、要点、影响判断、关系补充

缓存对象：

- `ClusterSummary`
- AI 输出原文
- 置信度
- impact 判断
- prompt/model 信息

这层是 AI 成本最高的一层，必须缓存。

## 5. 建议的数据模型

当前阶段可以继续使用本地 JSON 文件，不强制切数据库。

建议在 `backend/data/` 下新增结构：

```text
backend/data/
├── tasks/
├── cache/
│   ├── query_results/
│   ├── source_fetch/
│   ├── articles/
│   ├── article_extracts/
│   └── cluster_summaries/
```

### 5.1 query_results

用途：

- 存完全可复用的最终研究结果

建议 key：

```text
company_normalized + ticker + start_date + end_date + report_mode + schema_version
```

建议内容：

```json
{
  "query_key": "...",
  "created_at": "...",
  "task": {},
  "graph": {},
  "dependencies": {
    "article_ids": [],
    "cluster_keys": []
  }
}
```

### 5.2 source_fetch

用途：

- 存各数据源的抓取结果

建议 key：

```text
source + company_or_ticker + start_date + end_date
```

建议内容：

```json
{
  "cache_key": "...",
  "source": "google_news",
  "company_name": "Oracle",
  "ticker": "ORCL",
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "fetched_at": "...",
  "ttl_hours": 12,
  "items": []
}
```

### 5.3 articles

用途：

- 存标准化后的文章

建议 article_id：

```text
sha1(source_name + title + canonical_url)
```

建议内容：

```json
{
  "article_id": "...",
  "title": "...",
  "url": "...",
  "source_name": "...",
  "source_category": "official",
  "published_at": "...",
  "snippet": "...",
  "detail_score": 3,
  "company_candidates": ["Oracle", "ORCL"],
  "fetched_at": "..."
}
```

### 5.4 article_extracts

用途：

- 存单篇文章抽取结果

建议 key：

```text
article_id + extract_version
```

建议内容：

```json
{
  "extract_key": "...",
  "article_id": "...",
  "extract_version": "rules-v1",
  "event": {
    "event_type": "partnership",
    "event_label": "Partnership"
  },
  "entities": [],
  "relations": [],
  "summary": "...",
  "generated_by": "rules"
}
```

### 5.5 cluster_summaries

用途：

- 存事件簇级别总结和影响判断

建议 key：

```text
cluster_fingerprint + report_mode + model + prompt_version
```

其中 `cluster_fingerprint` 建议由以下内容计算：

- cluster 内 article_id 集合
- 代表事件类型
- 代表日期

建议内容：

```json
{
  "cluster_key": "...",
  "prompt_version": "cluster-summary-v2",
  "report_mode": "ai",
  "model": "claude-sonnet-4-6",
  "generated_at": "...",
  "summary": {}
}
```

## 6. 缓存键设计原则

缓存设计里最重要的是 key，否则会出现错复用。

### 6.1 必须纳入 key 的字段

- 公司标识
- ticker
- 时间范围
- 数据源
- report_mode
- model
- prompt_version
- schema_version

### 6.2 必须版本化的部分

以下内容一旦变动，旧缓存应视为不兼容：

- 事件分类规则
- 实体抽取逻辑
- 关系枚举
- LLM prompt
- Graph schema

建议统一维护几个常量：

```python
SCHEMA_VERSION = "graph-v1"
EXTRACT_VERSION = "rules-v1"
CLUSTER_PROMPT_VERSION = "cluster-summary-v1"
```

后续 key 都带上这些版本号。

## 7. 推荐复用策略

### 7.1 请求级复用

当以下条件全部一致时：

- 公司 / ticker 一致
- 起止日期一致
- report_mode 一致
- schema_version 一致

直接返回已有 `query_results`。

这是最快的一层。

### 7.2 数据源级复用

如果请求级未命中，则优先检查 `source_fetch`：

- 若缓存仍在 TTL 内，直接复用
- 若已过期，重新拉取并覆盖

建议 TTL：

- Google News: 6 到 12 小时
- Benzinga: 2 到 6 小时
- SEC EDGAR: 24 小时

SEC 更新频率较低，可以更长。

### 7.3 文章级复用

当拉取到的数据和历史文章重叠时：

- 先按 `article_id` 去重
- 对已有文章不再重复标准化
- 对已有 `article_extracts` 不再重复抽取

这层对热门公司收益很大。

### 7.4 事件簇级复用

完成文章集合后重新聚类：

- 若 cluster_fingerprint 命中，则直接复用历史 `ClusterSummary`
- 若 cluster 内文章发生变化，则只重算受影响 cluster

这能显著降低 AI 调用次数。

## 8. 与当前代码的映射关系

### 8.1 当前的切入点

最适合动手的位置：

- [backend/app/api/routes.py](/Users/bytedance/company-news-graph/backend/app/api/routes.py)
- [backend/app/services/storage.py](/Users/bytedance/company-news-graph/backend/app/services/storage.py)
- [backend/app/services/news_research.py](/Users/bytedance/company-news-graph/backend/app/services/news_research.py)

### 8.2 推荐的接入方式

#### Step 1

在 `routes.py` 的 `create_task()` 或 worker 启动前，先查 `query_results`。

如果命中：

- 直接创建一个 `completed` 任务
- 直接把 graph 填进 `_GRAPHS`
- 不再启动完整研究线程

#### Step 2

在 `news_research.py` 中把数据抓取逻辑拆成几个可缓存函数：

- `get_official_articles_with_cache()`
- `get_google_articles_with_cache()`
- `get_benzinga_articles_with_cache()`

#### Step 3

在事件抽取前增加文章级缓存：

- 对每篇文章生成 `article_id`
- 若已有 `article_extracts`，直接复用
- 没有才调用 `extract_event()`

#### Step 4

在 `summarize_cluster()` 外包一层缓存：

- 先算 `cluster_fingerprint`
- 查 `cluster_summaries`
- 未命中时才走 AI 或 rules summary

#### Step 5

在最终 `GraphResponse` 生成后，把 query 结果写入 `query_results`

这会和当前 `tasks/*.json` 共存，不冲突。

## 9. 增量更新策略

同一公司被频繁查询时，不应永远按“完整时间区间重抓”处理。

建议后续支持：

- 若用户查询 `2026-03-01 ~ 2026-03-31`
- 系统已有 `2026-03-01 ~ 2026-03-20`

则只补抓：

- `2026-03-21 ~ 2026-03-31`

然后把文章集合并，再重新聚类与组图。

这是第二阶段优化，不一定要首版就做，但数据模型应为此预留能力。

## 10. 失效与一致性策略

缓存不是永久正确的，必须允许失效。

### 10.1 需要失效的情况

- 新闻标题被修改
- 文章被删除
- 规则升级
- prompt 升级
- schema 升级

### 10.2 建议策略

- 原始抓取缓存采用 TTL
- 标准化文章层长期保存
- 抽取层和摘要层通过版本号失效
- 查询结果层可设置软过期时间，例如 24 小时

“软过期”含义是：

- 可以先返回已有结果
- 后台再异步刷新

当前项目先不必实现后台刷新，但设计上建议预留。

## 11. 为什么现在不必上数据库

当前阶段项目规模还不大，先用文件缓存是合理的。

原因：

- 开发成本低
- 易于观察和调试
- 与现有 `tasks/*.json` 模式一致
- 便于快速验证命中率和收益

建议演进路线：

1. 先用本地 JSON / 文件缓存验证方案
2. 缓存层稳定后，再切 SQLite
3. 规模再上去，再考虑 PostgreSQL / 对象存储 / 图数据库

如果直接跳数据库，容易把问题从“复用设计”变成“基础设施建设”。

## 12. 推荐的最小落地版本

如果只做一个最小但高收益版本，建议顺序如下：

### Phase 1

- 新增 `query_results` 级缓存
- 新增 `cluster_summaries` 级缓存

收益：

- 相同查询可秒级返回
- AI 成本显著下降

### Phase 2

- 新增 `source_fetch` 层
- 新增 `articles` 层

收益：

- 降低重复抓源
- 为后续增量更新打基础

### Phase 3

- 新增 `article_extracts`
- 引入跨时间范围复用

收益：

- 热门公司查询速度进一步提升
- 结构化数据可沉淀为研究资产

## 13. 对产品的直接价值

这套设计带来的收益不是抽象架构收益，而是很直接的产品收益：

- 更快：热门公司重复查询速度明显提升
- 更稳：减少外部源不稳定导致的波动
- 更省：减少重复 AI 调用
- 更可积累：中间数据不再只服务单次任务
- 更适合后续扩展：市场反应层、事件驱动分析、复杂检索都更容易接入

## 14. 结论

对于当前项目，最值得优先补的不是 GraphRAG，而是数据复用层。

因为当前瓶颈不是“知识检索不足”，而是：

- 重复抓取
- 重复抽取
- 重复摘要
- 中间结果没有沉淀

本项目下一阶段应把架构从：

- 一次性研究任务流水线

升级为：

- 可复用、可增量、可累积的事件驱动研究管线

这会比单纯增加新数据源或引入 GraphRAG 更早产生明确收益。
