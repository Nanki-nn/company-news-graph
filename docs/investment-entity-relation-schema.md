# 投资事件实体与关系 Schema

## 1. 目标

这个 schema 用来解决一个核心问题：

不要只把新闻总结成一段话，而要把投资研究真正关心的实体、关系和证据抽出来，作为图谱和后续分析的结构化输入。

适用范围：

- 公司动态研究
- 投资情报图谱
- 事件驱动型研究
- 财报、监管、并购、裁员、合作等场景

## 2. 设计原则

### 2.1 事件优先

不是“文章里提到什么实体”，而是：

- 这篇文章对应什么事件
- 哪些实体是这个事件的核心参与方
- 这些实体之间是什么关系

### 2.2 核心实体优先

不要把文中所有实体都画进图里。

需要区分：

- `core_entities`
  事件真正相关的核心实体
- `mentioned_entities`
  只是提到，但不一定值得入图的实体

图谱默认只用 `core_entities`。

### 2.3 投资场景优先

这个 schema 不是通用知识图谱 schema。

它优先服务以下判断：

- 这是什么投资事件
- 涉及哪些关键实体
- 是官方披露还是媒体报道
- 对股价和基本面可能有什么影响

## 3. 顶层结构

建议 AI 直接输出如下 JSON：

```json
{
  "event": {},
  "entities": {
    "core": {},
    "mentioned": {}
  },
  "relations": [],
  "evidence": [],
  "assessment": {}
}
```

## 4. Event 结构

```json
{
  "event_type": "earnings_result",
  "event_title": "甲骨文第三季度业绩超预期",
  "event_summary": "甲骨文公布第三季度财报，收入和云业务增速均高于市场预期。",
  "event_date": "2026-03-10",
  "event_stage": "result",
  "source_type": "media",
  "officialness": "mixed"
}
```

字段说明：

- `event_type`
  推荐枚举：
  - `earnings_schedule`
  - `earnings_result`
  - `guidance_update`
  - `acquisition`
  - `partnership`
  - `layoffs`
  - `regulation`
  - `capital_markets`
  - `leadership_change`
  - `product_launch`
  - `major_customer`
  - `supply_chain_change`
  - `analyst_rating`
  - `price_move`
  - `news`

- `event_title`
  面向用户展示的短标题

- `event_summary`
  80-180 字的结构化摘要

- `event_date`
  事件发生日期，优先事件日期，其次文章日期

- `event_stage`
  可选：
  - `schedule`
  - `announced`
  - `result`
  - `ongoing`
  - `closed`

- `source_type`
  - `official`
  - `media`
  - `mixed`

- `officialness`
  与 `source_type` 类似，但保留为分析维度

## 5. Entities 结构

### 5.1 core.entities

```json
{
  "companies": [
    {
      "name": "Oracle",
      "ticker": "ORCL",
      "role": "subject"
    },
    {
      "name": "NetSuite",
      "ticker": "",
      "role": "subsidiary"
    }
  ],
  "people": [
    {
      "name": "Safra Catz",
      "role": "executive"
    }
  ],
  "products": [
    {
      "name": "Oracle Database 23ai",
      "role": "launched_product"
    }
  ],
  "locations": [
    {
      "name": "United States",
      "role": "affected_region"
    }
  ],
  "regulators": [
    {
      "name": "SEC",
      "role": "regulator"
    }
  ]
}
```

建议核心实体类型：

- `companies`
- `people`
- `products`
- `locations`
- `regulators`
- `organizations`

### 5.2 mentioned.entities

这个区只做保留，不默认入图。

适合放：

- 文中顺带提到的竞争对手
- 无关紧要的地名
- 无关紧要的媒体机构

## 6. Relations 结构

关系是这个 schema 里最重要的部分之一。

### 6.1 关系示例

```json
[
  {
    "type": "PARTNERED_WITH",
    "source": "Oracle",
    "target": "NetSuite",
    "confidence": "high"
  },
  {
    "type": "CUT_JOBS_IN",
    "source": "Oracle",
    "target": "United States",
    "confidence": "medium"
  }
]
```

### 6.2 推荐关系枚举

- `PARTNERED_WITH`
- `ACQUIRED`
- `LAUNCHED`
- `CUT_JOBS`
- `CUT_JOBS_IN`
- `INVESTIGATED_BY`
- `SUED_BY`
- `APPOINTED`
- `LEFT`
- `GUIDED`
- `REPORTED_IN`
- `FILED`
- `COMPETES_WITH`
- `AFFECTED_PRICE`

### 6.3 关于竞争关系

`COMPETES_WITH` 不建议早期默认强抽。

原因：

- 误报率很高
- 很多文章只是比较，不代表真实竞争事件

建议做法：

- 先放在 `mentioned_entities`
- 或仅在明确出现 `rival`, `competes with`, `market share against` 时才提取

## 7. Evidence 结构

```json
[
  {
    "source_name": "CNBC",
    "source_url": "https://example.com",
    "published_date": "2026-03-10",
    "quote": "Oracle stock jumps 10% on earnings beat and increased guidance...",
    "supports": ["event_summary", "impact_direction", "event_type"]
  }
]
```

每条重要结论都应尽量有证据。

## 8. Assessment 结构

```json
{
  "impact_direction": "positive",
  "impact_level": "high",
  "price_sensitive": true,
  "confidence": "medium",
  "why_it_matters": "财报超预期且指引上修，可能强化市场对云业务增长的预期。"
}
```

建议字段：

- `impact_direction`
  - `positive`
  - `negative`
  - `neutral`

- `impact_level`
  - `high`
  - `medium`
  - `low`

- `price_sensitive`
  - `true`
  - `false`

- `confidence`
  - `high`
  - `medium`
  - `low`

- `why_it_matters`
  解释它为什么值得投资者关注

## 9. 最小可落地版本

MVP 不要一开始追求全量。

建议先落这套最小字段：

```json
{
  "event": {
    "event_type": "",
    "event_title": "",
    "event_summary": "",
    "event_date": "",
    "officialness": ""
  },
  "entities": {
    "core": {
      "companies": [],
      "people": [],
      "products": [],
      "locations": [],
      "regulators": []
    }
  },
  "relations": [],
  "assessment": {
    "impact_direction": "",
    "impact_level": "",
    "price_sensitive": false,
    "confidence": ""
  }
}
```

## 10. 推荐接入顺序

### Phase 1

- 先做：
  - `companies`
  - `people`
  - `products`
  - `locations`
  - `regulators`
- 先做关系：
  - `PARTNERED_WITH`
  - `ACQUIRED`
  - `INVESTIGATED_BY`
  - `APPOINTED`
  - `LAUNCHED`
  - `CUT_JOBS_IN`

### Phase 2

- 增加：
  - `organizations`
  - `major_customer`
  - `supply_chain_change`
  - `analyst_rating`

### Phase 3

- 谨慎增加：
  - `COMPETES_WITH`

## 11. 一句话建议

不要先做“文章里的全量实体抽取”，而要先做“投资事件驱动的核心实体与关系抽取”。

只有这样，图谱才会越来越像投资情报产品，而不是新闻可视化工具。
