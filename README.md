# RELATER

`RELATER` 是论文 **Unsupervised Graph-based Entity Resolution for Complex Entities** 的实现代码。

实体解析（Entity Resolution, ER）是在没有唯一实体标识符的情况下，将不同数据库中属于同一实体的记录链接起来的过程。`RELATER` 是一个无监督的基于图的实体解析框架，专注于解决复杂实体的解析挑战。该框架提出了全局方法来传播链接决策、利用歧义信息、自适应地融合关系结构，以及通过动态精炼步骤改善记录聚类。

---

## 快速开始（Python 3）

```bash
conda create -n relater-py3 -y python=3.12
conda activate relater-py3
pip install -r requirements-py3.txt
```

### 文献数据集（dblp-acm1, dblp-scholar1）

```bash
# dblp-acm1 基线
python3 RELATER/run_relater.py dblp-acm1 \
  --atomic-t 0.9 --bootstrap-t 0.95 --merge-t 0.8 --wa 1.0 --bridges-n 10

# dblp-scholar1 + 向量检索
HF_ENDPOINT=https://hf-mirror.com python3 RELATER/run_relater.py dblp-scholar1 \
  --atomic-t 0.9 --bootstrap-t 0.95 --merge-t 0.8 --wa 1.0 --bridges-n 10 \
  --use-vector-blocking --vector-top-k 200 --vector-min-cosine 0.1 --vector-sim-blend 0.2

# 使用 YAML 配置文件
python3 RELATER/run_relater.py --config config/examples/dblp-acm1.yaml
```

### IPUMS（人口普查记录链接）

```bash
cd RELATER
python3 -c "
import sys, os
sys.argv = ['hh_er', 'ipums', '0.9', '0.95', '0.8', '1.0', '10']
import runpy
runpy.run_module('er.hh_er', run_name='__main__')
"
```

输出保存在 `out/<数据集名>/` 下，最终结果写入 `out/<数据集名>/er/results.csv`。

---

## 支持的数据集

| 数据集 | 类型 | 数据位置 | 入口脚本 |
|--------|------|----------|----------|
| `dblp-acm1` | 文献（DBLP vs ACM） | `data/dblp-acm1/` | `run_relater.py` |
| `dblp-scholar1` | 文献（DBLP vs Scholar） | `data/dblp-scholar1/` | `run_relater.py` |
| `ipums` | 人口普查（1870-1880） | `data/ipums/` | `er/hh_er.py` |
| `ios` | 民政记录（苏格兰 Skye 岛） | 需单独获取 | `er/civil_er.py` |
| `kil` | 民政记录（苏格兰 Kilmarnock） | 需单独获取 | `er/civil_er.py` |
| `bhic` | 民政记录（荷兰） | 需单独获取 | `er/civil_er.py` |
| `mb` | 音乐（MusicBrainz） | 需单独获取 | `er/sg_er.py` |
| `msd` | 音乐（Million Song） | 需单独获取 | `er/sg_er.py` |

`data/` 目录下已包含 `dblp-acm1`、`dblp-scholar1` 和 `ipums` 的数据文件，其余数据集需要自行准备。

---

## 实验结果

### dblp-acm1

| 方法 | Precision | Recall | F1 |
|------|-----------|--------|------|
| RELATER 基线（merge_t=0.8, wa=1.0） | 99.39 | 94.68 | **94.13** |
| RELATER + 向量检索（k=100, cos=0.3, blend=0.2） | 99.38 | 94.23 | 93.69 |

### dblp-scholar1

| 方法 | Precision | Recall | F1 |
|------|-----------|--------|------|
| RELATER + 向量检索（k=200, cos=0.1, blend=0.2） | 99.75 | 45.28 | **45.23** |

### IPUMS（1870-1880 人口普查链接）

| 链接类型 | GT | TP | FP | FN | Precision | Recall | F1 |
|----------|------|------|------|------|-----------|--------|------|
| F-F（父亲） | 10,914 | 10,586 | 0 | 328 | 100.0 | 96.99 | **96.99** |
| M-M（母亲） | 10,908 | 10,530 | 0 | 378 | 100.0 | 96.53 | **96.53** |
| C-C（儿童） | 16,875 | 15,750 | 2,036 | 1,125 | 88.55 | 93.33 | **83.28** |

---

## 向量检索（可选功能）

本仓库在原始 RELATER 基础上增加了基于 FAISS 的向量检索功能，用近似最近邻搜索替代暴力 O(N×M) 候选对生成，使用 sentence-transformers 词嵌入计算语义相似度。

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--use-vector-blocking` | false | 启用向量检索 |
| `--vector-model` | all-MiniLM-L6-v2 | Sentence-transformers 模型名 |
| `--vector-top-k` | 50 | 每个查询的最近邻数量 |
| `--vector-min-cosine` | 0.5 | 最小余弦相似度阈值 |
| `--vector-sim-blend` | 0.0 | 混合权重：`sim = JW×(1-b) + cosine×b` |
| `--vector-hnsw-m` | 32 | HNSW 索引 M 参数 |
| `--vector-hnsw-ef-construction` | 128 | HNSW 构建参数 |
| `--vector-hnsw-ef-search` | 128 | HNSW 搜索参数 |

启用后采用混合策略：
- **向量检索**：长文本属性（论文标题），通过 FAISS + 嵌入向量
- **暴力匹配**：短属性（姓、名、年份），通过 Jaro-Winkler / MAD

### 新增文件

| 文件 | 用途 |
|------|------|
| `RELATER/common/embedding.py` | 模型加载、文本嵌入与缓存 |
| `RELATER/common/vector_index.py` | FAISS HNSW 索引构建与搜索 |
| `RELATER/common/vector_blocking.py` | 混合原子节点与文献对阻断 |
| `config/examples/dblp-acm1-vector.yaml` | 启用向量检索的配置示例 |

---

## 数据格式

文献数据集（dblp-acm1, dblp-scholar1）遵循 DeepMatcher 标准格式：

- **tableA.csv** / **tableB.csv** — 两个数据源的记录
- **train.csv** / **valid.csv** / **test.csv** — 标注好的配对数据，供有监督方法使用（RELATER 不使用）
  - 格式：`ltable_id, rtable_id, label`（1=匹配, 0=不匹配）

RELATER 是**无监督**方法，仅使用 tableA 和 tableB。Ground truth 在代码内部生成。

IPUMS 使用单个 `census_1870-1880_couples.csv` 文件，包含两次普查的所有记录。Ground truth 通过配对记录结构推导（同一个人在 1870 年和 1880 年各有一条记录，交替排列）。

---

## 时间约束

根据论文中的领域知识，设定以下时间约束。约束因数据集而异。

##### IOS 和 KIL

* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Bm) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>) &ge; 55) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Bf) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Mm) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Dd) ^
IsAfter(r<sub>i</sub>, r<sub>j</sub>) ^ AlmostSameBirthYears(r<sub>i</sub>,
r<sub>j</sub>) &rarr; ValidMerge (r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Ds) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Dp) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Mbp) ^ (30 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Mgp) ^ (30 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bp) ^ (r<sub>j</sub>.&rho; = Bp) ^ (9 &le;
MonthTimeGap(r<sub>i</sub>, r<sub>j</sub>)) ^ AlmostSameMarriageYears(r<sub>i</sub>, r<sub>j</sub>) &rarr; ValidMerge
(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bp) ^ (r<sub>j</sub>.&rho; = Mm) ^ AlmostSameMarriageYears(r<sub>i</sub>, r<sub>j</sub>) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bm) ^ (r<sub>j</sub>.&rho; = Dd) ^
IsAfter(r<sub>i</sub>, r<sub>j</sub>) &rarr; ValidMerge(r<sub>i</sub>,
r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bf) ^ (r<sub>j</sub>.&rho; = Dd) ^
(9 &le; MonthTimeGap(r<sub>i</sub>, r<sub>j</sub>) ) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mm) ^ (r<sub>j</sub>.&rho; = Mm) ^
AlmostSameBirthYears(r<sub>i</sub>, r<sub>j</sub>) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mm) ^ (r<sub>j</sub>.&rho; = Dd) ^
IsAfter(r<sub>i</sub>, r<sub>j</sub>) ^ AlmostSameBirthYears(r<sub>i</sub>,
r<sub>j</sub>) &rarr; ValidMerge (r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mm) ^ (r<sub>j</sub>.&rho; = Mbp) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mm) ^ (r<sub>j</sub>.&rho; = Mgp) ^ (15 &ge;
YearTimeGap(r<sub>i</sub>, r<sub>j</sub>)) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)

---

## 链接约束

##### IOS 和 KIL

* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) ^ (|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Bp) ^
(|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Mm) ^
(|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Mbp) ^
(|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Mgp) ^
(|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Ds) ^
(|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bb) ^ (r<sub>j</sub>.&rho; = Dp) ^
(|Links(r<sub>j</sub>,Bb)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Bp) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mm) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mbp) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Mgp) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Ds) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = Dp) ^ (r<sub>j</sub>.&rho; = Dd) ^
(|Links(r<sub>i</sub>,Dd)| = 0) &rarr; ValidMerge(r<sub>i</sub>, r<sub>j</sub>)

##### IPUMS
* (r<sub>i</sub>.&rho; = F) ^ (r<sub>j</sub>.&rho; = F) ^
(|Links(r<sub>i</sub>,F)| = 0) ^ (|Links(r<sub>j</sub>,F)| = 0) &rarr;
ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = M) ^ (r<sub>j</sub>.&rho; = M) ^
(|Links(r<sub>i</sub>,M)| = 0) ^ (|Links(r<sub>j</sub>,M)| = 0) &rarr;
ValidMerge(r<sub>i</sub>, r<sub>j</sub>)
* (r<sub>i</sub>.&rho; = C) ^ (r<sub>j</sub>.&rho; = C) ^
(|Links(r<sub>i</sub>,C)| = 0) ^ (|Links(r<sub>j</sub>,C)| = 0) &rarr;
ValidMerge(r<sub>i</sub>, r<sub>j</sub>)

---

## 项目结构

| 目录 | 内容 |
|------|------|
| `common/` | 工具函数、相似度计算、向量检索 |
| `data/` | 数据读取与预处理 |
| `er/` | ER 算法（bib_graph、hh_graph、civil_graph、sg_graph） |
| `febrl/` | 来自 FEBRL 的字符串相似度函数 |
| `config/examples/` | YAML 配置文件 |
| `experiments/` | 实验脚本与结果 |

## 依赖

- [Python 3.10+](https://www.python.org)
- [NetworkX](https://networkx.org/)
- [Pandas](http://www.scipy.org)
- [PyYAML](https://pyyaml.org/)（YAML 配置支持）

可选依赖（向量检索功能）：
- [sentence-transformers](https://www.sbert.net/)
- [faiss-gpu](https://github.com/facebookresearch/faiss)

安装：`pip install -r requirements-py3.txt`

## 许可证

本程序为自由软件：您可以根据自由软件基金会发布的 GNU 通用公共许可证（第 3 版或更新版本）的条款重新分发和/或修改它。

## 联系方式

原始作者：[nishadi.kirielle@anu.edu.au](mailto:nishadi.kirielle@anu.edu.au)
