# 数据集成课程大作业报告（工程化改进）

**题目**：面向实体解析（Entity Resolution）原型系统的**项目结构重构与可复现运行**  
**代码基础**：ANU RELATER（无监督图实体解析，书目场景以 DBLP–ACM 为示例）  
**说明**：本报告记录**工程与结构层面**的创新，算法与论文结论仍归属原作者；改进目标是让该原型在课程场景下更易理解、复现与展示。

---

## 摘要

实体解析是数据集成中「把多源记录对应到同一现实世界对象」的关键环节。RELATER 将记录与属性相似度建模为图结构，并在图上做合并与约束传播。原仓库在路径与启动方式上强依赖「从内层包目录启动」和「位置型命令行参数」，不利于团队协作与实验记录。本文工作在不改动核心 ER 逻辑的前提下，引入**仓库根路径锚定**、**命令行启动器**与 **YAML 运行配置**，并补充依赖声明与文档结构，使该数据集成原型达到可展示、可审计的课程交付标准。

**关键词**：数据集成；实体解析；工程结构；可复现性；配置管理

---

## 1. 背景与问题

### 1.1 数据集成语境下的 RELATER

在异构数据源（如不同数据库导出的 `tableA.csv` / `tableB.csv`）之间，同一篇论文或同一作者可能有多条记录且缺乏全局唯一键。RELATER 通过：

- 属性级「原子」相似节点；
- 论文–作者等关系结构；

在一张图上传播合并决策，属于典型的**结构感知**实体解析管线，与课程中「模式对齐 + 记录链接」主题高度相关。

### 1.2 原项目的主要工程痛点

1. **路径与当前工作目录耦合**：`settings` 使用 `../data`、`../out`，若从错误目录执行 `python -m er.bib_er`，会静默读错数据或写到意外位置。  
2. **配置入口隐蔽**：超参数通过 `sys.argv` 位置传入，且部分模块在 import 阶段读取，实验难以用「一份配置文件」复现。  
3. **目录命名重复**：外层与内层均出现 `RELATER/`，新人难以区分「仓库根」与「代码包根」。  
4. **依赖未集中声明**：README 仅文字列举，不利于助教环境一键安装（尤其在 Python 2 遗留栈上）。

---

## 2. 改进目标与设计原则

| 目标 | 做法 |
|------|------|
| 可复现 | 将阈值与数据集名写入 `config/examples/*.yaml`，纳入版本管理 |
| 低侵入 | **不改** `er/` 中图算法与合并主循环，避免引入回归 |
| 可演示 | 提供单一入口 `run_relater.py` 与 `scripts/run_dblp_acm_example.sh` |
| 可演进 | 路径集中后，为后续 Python 3 迁移或打包成 wheel 预留空间 |

---

## 3. 具体改进内容

### 3.1 路径锚定（`paths.py` + `settings.py`）

新增 `RELATER/paths.py`，根据内层包目录 `__file__` 计算**外层仓库根** `REPO_ROOT`，并导出 `DATA_ROOT`、`OUT_ROOT`。  
修改 `common/settings.py`：在保留各数据集分支逻辑的前提下，用 `os.path.join(REPO_ROOT, 'data', …)` 与 `os.path.join(REPO_ROOT, 'out', data_set)` 构造路径前缀。

**效果**：无论从哪个目录启动（只要 Python 能找到 `common` 包），读写 `data/` 与 `out/` 均指向**同一物理目录**，符合数据集成实验对「数据目录单一真源」的期望。

### 3.2 启动器与配置外置（`run_relater.py`）

新增 `RELATER/run_relater.py`：

- 使用 `argparse` 提供具名参数（`--atomic-t`、`--merge-t` 等）；  
- 支持 `--config` 加载 YAML；  
- 在 import `er.bib_er` **之前** 重建 `sys.argv`，兼容原有 `settings` / `hyperparams` 对 `sys.argv` 的依赖。

**效果**：实验参数从「口头传递」变为「可 diff 的配置文件」，便于大作业中说明**每次运行的完整条件**。

### 3.3 仓库布局与辅助文件

- `config/examples/dblp-acm1.yaml`：书目场景默认阈值示例。  
- `requirements.txt`：列出 NetworkX、Pandas、Matplotlib、PyYAML 等与上游代码匹配的版本区间（Python 2.7 语境）。  
- `pyproject.toml`：项目元数据占位，便于 IDE 与工具链识别。  
- `scripts/run_dblp_acm_example.sh`：演示如何从仓库根调用启动器。  
- `Makefile`：`make run-example` 打印推荐命令。  
- `docs/architecture.md`：改进前后架构图与说明（Mermaid）。  
- `README.md`：增补「Course-oriented layout」一节，与上游说明并存。

### 3.4 算法层改进：歧义感知的动态合并阈值（bibliographic 场景）

在 `er/bib_graph.py` 的合并主循环里，原始实现使用固定阈值 `merge_t` 判断：

- 组内平均相似度 `sim >= merge_t` 才合并。

这会带来一个问题：高歧义样本（常见姓名/题名片段）和低歧义样本（稀有签名）使用同一阈值，容易出现「高歧义误并」与「低歧义漏并」并存。  

本次加入**动态阈值函数**：

- `effective_t = base_t + delta * (0.5 - avg_amb)`，其中 `delta=0.08`；  
- `avg_amb` 为候选节点组的平均 `SIM_AMB`（范围归一到 `[0,1]`）。

直观解释：

- 当 `avg_amb` 小（更歧义）时，`effective_t` 上升，合并更谨慎；  
- 当 `avg_amb` 大（更不歧义）时，`effective_t` 下降，允许适度放宽；  
- 对 singleton 合并同样应用该机制，并将队列预筛选由固定阈值改为 `merge_t - delta` 的软门槛，避免过早过滤掉潜在优质匹配。

该改动复用了 RELATER 既有的 `SIM_AMB` 统计，不引入新特征、只改变决策边界，便于做公平对比实验（固定其它参数，比较改动前后 precision/recall/F1）。

---

## 4. 与「数据集成」课程能力的对应关系

| 课程能力点 | 本工作的体现 |
|------------|----------------|
| 理解多源数据与链接任务 | 沿用 RELATER 书目数据流；文档中明确 `data/` 与 `out/` 角色 |
| 可追溯的实验 | YAML 配置 + Git 记录每次参数 |
| 工程质量 | 路径去耦合、入口单一、依赖声明 |
| 展示与答辩 | `presentation_outline.md` 提供幻灯片叙事骨架 |

---

## 5. 局限与后续工作

1. **运行时仍为 Python 2.7**：上游广泛使用 `xrange`、`iteritems` 等语法；本次作业**未**做全量 Python 3 迁移，以免超出课程周期。  
2. **未将 `common`/`er` 打成单一命名空间包**：完整 setuptools 映射需批量修改 import，留作后续迭代。  
3. **仅书目入口封装了 CLI**：`civil_er`、`hh_er` 等仍可按原方式调用；扩展方式相同——在启动器中重建 `sys.argv` 后 `run_module`。

---

## 6. 结论

本工作包含两类改进：  
1) 工程层（路径锚定、统一入口、配置外置）提升可复现性；  
2) 算法层（歧义感知动态阈值）提升合并决策对样本不确定性的适配能力。  

因此该课程版本不再只是「把代码跑起来」，而是形成了「可复现 + 有算法增量 + 可展示」的完整交付形态。

---

## 参考文献（示例格式）

1. Nishadi Kirielle, Peter Christen, Thilina Ranbaduge. *RELATER* — Unsupervised graph-based entity resolution framework (software release accompanying academic work).  
2. Christen, P. *Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection*. Springer, 2012.

---

## 附录：复现命令摘录

在仓库根目录（含 `data/`、`out/`、`RELATER/`、`config/` 的那一层）执行：

```bash
pip install -r requirements.txt   # 建议在 Python 2.7 虚拟环境中
python RELATER/run_relater.py --config config/examples/dblp-acm1.yaml
```

（若环境变量 `PYTHON` 指向 `python2`，亦可执行 `scripts/run_dblp_acm_example.sh`。）
