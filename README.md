# xhs-infographic

把一句话的选题，做成一套小红书图文：**先判能不能做，再做 3（或 4）张 3:4 信息图 + 1 份标注 docx**。

这是把一份真实在用的手工 SOP + 客户官方规则总纲，固化成可复用的 skill —— 里面每一条判定，都来自一次交付后被指出的错，或客户明确写死的扣分项。

## 它解决什么问题

同一件事做过几十遍之后，难点不再是"会不会做"：

- 拿到选题不知道**该不该做** —— 界面操作类做完也是 1 分不合格，整批白做
- 每次都要重新回忆"第一页标题取哪个、副标题取哪个"
- 知道"图是准绳"，一忙起来还是先改了文档
- 三张图尺寸各不一样，看着像一套，交付才发现有一张是方图
- 正文里顺手写了个 `help.xxx.com` —— 那是**红线**，直接算错
- 链接又给了个首页，用户点开还得自己翻

skill 把这些判断写成规则、把确定性的事写成脚本，让每次产出的形状一致。

## 流水线

```
主题 / txt
  → 第 -1 步：判题材（一票否决 + 三层过滤 + 需求类型）
  → 第 0 步：备份清空、口令在位、余额、深链
  → 第 1 步：DeepSeek 出文案（口令原文，只换主题）
  → 第 2 步：按映射表填数漫提示词
  → 第 3 步：数漫 GEM 3.8 flash 出图
  → 第 4 步：逐张下载 + 尺寸/完整度核对 + 校验值查重
  → 第 5 步：尺寸归口 864×1152
  → 第 6 步：质检（逐字读、小字放大 3 倍、四条硬伤）
  → 第 7 步：copy.json → docx（正文里禁止出现网址）
  → 第 8 步：交付自检（脚本 + 肉眼清单）
  → 第 9 步：备份归档 + 复盘进 SOP
```

## 目录

```
xhs-infographic/
├── SKILL.md                     # 触发条件、契约、主流程、11 条红线
├── references/
│   ├── topic-gate.md            # 第 -1 步：三层过滤、需求类型、10 类笔记、12 项不生产
│   ├── pipeline.md              # 十步细节、标题/正文/配图硬指标、断点恢复
│   ├── browser-notes.md         # 数漫/DeepSeek/下载的实操坑与坐标
│   └── delivery-check.md        # 交付前自检清单 + 三分自查四问
├── scripts/
│   ├── normalize_images.py      # 尺寸归口、方图补边、编号连续性、查重
│   ├── build_docx.py            # copy.json → docx（含网址拦截）
│   ├── verify_link.py           # 深链判定
│   └── check_delivery.py        # 只读交付自检（含红线 11 网址扫描）
├── assets/
│   ├── deepseek-prompt.txt      # 文案口令原文
│   ├── suman-template.txt       # 出图模板原文
│   └── template.docx            # 版式模板（正文已清空，只留样式）
└── examples/tricycle.json       # 一批真实文案，copy.json 的格式样例
```

## 安装

```bash
git clone <repo> ~/.workbuddy/skills/xhs-infographic
```

或直接把目录拷进 `~/.workbuddy/skills/`，重启 WorkBuddy 后生效（技能只在启动时扫描一次）。

## 用法

对话里说「用这个主题出一批：<主题>」，或「这个能不能做：<主题>」。

单个脚本也能单独用：

```bash
python scripts/normalize_images.py --dir "…/数据标注" --dry-run
python scripts/build_docx.py --copy examples/tricycle.json --out "…/标题.docx"
python scripts/verify_link.py "https://example.com/a/123" 关键词1 关键词2
python scripts/check_delivery.py --dir "…/数据标注"
```

## 设计上的四个取舍

**① 权威源只有一个。**
`桌面\提示词与SOP\小红书出图SOP.md` 是唯一权威版，`references/` 只是它的执行快照。冲突时按 SOP，并把差异报出来。之前那份独立的「失误档案」已并入 SOP，本 skill 不再维护第二份规则文件 —— 两套规则必然漂移。

**② 文案结构写成中间文件，不直接写 XML。**
`copy.json` 是文案结构，`build_docx.py` 是排版。结构错了改 json 几秒重出，排版永远由脚本决定。实测：用它重跑一批已交付文档，26 个段落逐段完全一致。

**③ 能判定的错，做成脚本拦住。**
"正文被拆段""链接行加了站名""表情标题前缺空行""正文里出现网址""编号不连续""三张校验值重复"，这些不靠自觉，靠 `check_delivery.py` 报红。肉眼管错别字和画风，脚本管形状。

**④ 浏览器那几步不硬自动化。**
出图、下载依赖登录态和页面结构，写成死脚本一周就失效。所以保留现场判断，只把**判定条件**（截图确认第几页、看原图尺寸、校验值查重、失败两次单页重发）写死。

## 已知限制

- 数漫、DeepSeek 需要本机已有登录态，脚本不做任何登录动作
- 图上的错别字、画风一致性、留白与"传单感"仍需肉眼质检
- `assets/` 里的口令是个人写作风格，换人用需要改
- 交付目录、下载目录是硬编码的本机路径，换机器先改 `SKILL.md` 那张路径表
- 题材判断是判断题，skill 给的是判定表，不是保证正确的答案

## 安全说明

- 不含任何账号、Cookie、token，也不读取登录态文件
- 所有网络请求只发往用户指定的页面（`verify_link.py` 只抓目标 URL）
- `template.docx` 的正文已清空，只保留样式

## License

MIT
