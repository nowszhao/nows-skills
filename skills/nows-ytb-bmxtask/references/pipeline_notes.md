# YouTube 侧实测结论（2026-10）

## 1. CDP 抓「内容转文字」面板：已不可用

备份版技能（`nows-ytb-bilingualex.backup-20260806-2353`）要求用 CDP 驱动本机 Chrome
打开视频页、点开「内容转文字」面板、读 innerText。实测：

- `lsof` 显示 Chrome 确实在监听 `127.0.0.1:9222`；
- 但 `/json/version`、`/json/list`、`/json` **全部返回 404**，任何本地 CDP/代理连接都拿不到 target。

结论：不要再尝试这条路径，也不要为此去引导用户开启远程调试。改用 yt-dlp 直取官方 ASR——
timedtext 数据与转写面板同源，聚合后等价。

## 2. bot 检查：所有 yt-dlp 调用都要带 cookies

不带 cookies 的 `yt-dlp -J` 直接报：

```
ERROR: [youtube] <id>: Sign in to confirm you're not a bot.
```

加上 `--cookies-from-browser chrome` 即恢复正常（本机一次提取 3132 个 cookie）。
下载、元数据探测、ASR 拉取三处都要带。

## 3. 聚合参数

```bash
python3 <YTB2>/scripts/aggregate_srt.py raw_asr.en.srt transcript_official.srt \
    --max-gap 700 --max-group 7500 --max-words 26
```

实测 31 分钟视频：1185 个滚动窗口碎片 → 280 句。
`--max-words 26` 是词数硬兜底；标点/停顿信号失效时保证单行不会无限变长。

## 4. ASR 纠错：章节标题 + 简介是最强证据

ASR 把专有名词念错得毫无规律。**先 `yt-dlp -J` 拿 `chapters` 和 `description`，
再开始翻译**，能一次校准绝大部分专名。真实例子（Arena AI 一期模型横评）：

| ASR 听到的 | 正确写法 | 来源 |
| --- | --- | --- |
| 61 Soul / 56.1 Soul / SOPUS | GPT-6.1 Sol | 标题 + 章节 |
| Sony 55 / sonet / Sonya | Sonnet 5.5 | 标题 |
| Astro / ASA | Astra | 简介 |
| Oppus / Kopus | Opus | 简介 |
| Tower of Bubble | Tower of Babel | 章节 |
| x High | xHigh | 章节上下文 |
| Kimik 3 | Kimi K3 | 上下文 |
| Kopus（西西弗斯处） | Sisyphus | 章节 |
| hairstyle race / turtle with hair | tortoise and the hare | 章节 |
| open anthropic / open-eyed models | OpenAI models | 语义 + 简介 |

其他高频错型：`which→who`、数字串（`$222 23`→`$2.23`、`five dollars 5`→`$5.05`）、
多余冠词、语气词 `uh/um` 粘连、句子被切成两半。

## 5. 工具会话环境问题

Bash 环境里带 `http_proxy=127.0.0.1:59348`，访问**本机端口**必须加 `--noproxy '*'`，
否则请求会被沙箱代理吞掉（表现为 404 / 空响应 / `upstream connect failed`）。
排查本机服务时先：

```bash
curl -s --noproxy '*' -m 6 http://127.0.0.1:9222/json/version
```

`ps` 与部分 `lsof` 在沙箱里可能不可用或输出不完整，不要据此判断进程状态。

## 6. ASR 陷阱补充（第二批实测）

同一个专名**在不同位置会被错成不同写法**，只改第一处没用，必须建对照表后全文统一。
实例（AI Engineer / Laurie Voss 那期，同一份转写里）：

- `Meter` / `Miter` → **METR**（同一期里两种错法）
- `Codeex` → **Codex**；`Cursor Browser` → **Cursor BugBot**
- `Andriy Karpaty` → **Andrej Karpathy**；`Dexter Horty` → **Dex Horthy**
- `Sarah Goh` / `Sarah Kuo` → **Sarah Guo**；`Swebench` / `SWE-Bench` → **SWE-bench**
- `Arise AI` → **Arize AI**；`Devon` → **Devin**；`Frontierbench` → **FrontierCode**

其他两类高频情况：

- **被过滤掉的专名**：转写里会出现 `[the company]` 这类占位（本片 Bun 的归属被吞掉）。
  处理原则：能从公开事实高置信度还原就还原（Bun 已并入 Anthropic），否则保持模糊，
  **不要为了顺口编一个名字**。
- **语义被 ASR 反转**：本片出现过 `This means stopping checking PRs`，结合上下文其实是
  「**不**是说你该停止审查 PR」。遇到和段落主旨矛盾的短句，按主旨校正，不要直译。

## 7. 文件命名（会影响后续所有命令）

- `download.py` 只替换 `:` `|` `*` 等字符（本片 `Review: What` → `Review_ What`），
  **空格和破折号 `—` 会原样留在文件名里**。所以所有 shell/脚本传参都必须加引号。
- `assemble_final.py` 会自动让 `.ass` 与 MP4 同名，交付前确认两者 stem 一致。
- 中文标题、emoji 标题同样可用，不需要手工改名。

## 8. 交付前自查清单

- `grep -E "cheering|applause|laughter|欢呼|掌声|笑声"` → 应为 0
- `grep "您"` → 应为 0（访谈统一用「你」）
- 中文字数 ÷ 覆盖秒数 ≈ 4–5 字/秒为 TTS 舒适区（实测本片 4.2）
- `assemble_final.py` 与 `bmx subtitle parse` 双双通过

## 9. 断句质量：机械聚合 vs FULL 重断句（2026-10 定论）

**2026-10 之前所有片子走的都是纯机械聚合**（`aggregate_srt.py` 后直接翻译），
没有跑 `refine_srt.py`。结果是可量化的：

- 一部 156 行的片子里，**53 行英文以虚词结尾**（and/the/to/of/that…），
  **9 行中文以标点或连词开头**（「。我叫…」「而是在…」）—— 一句话被切成两半。
- 大量 1–2 秒碎片行（「嗯。」「是的。」），平均语速被拉低到 4–5 字/秒
  （正常访谈应在 5.5 左右）。这不是翻译漏字，是断句切碎了。

**修法**：Step 6 的 FULL 重断句（`prepare-full` → `check_refined` → `apply`），
模型按语义重排，允许跨行合并，输出 `transcript_refined.srt`，再拿它去切分翻译。
代价：多一轮全片模型调用（长视频 +30% 耗时），且行数变了 → **翻译必须全部重做**。

**唯一铁律**：refine 分块里**一个词都不能删**，包括 `uh/um`、`the the`、`and/to`。
约 20% 的分块会漂，漂了就单独重派该块；禁止用脚本插词补回（破坏词序，apply 照样塌缩）。

## 10. 无语音视频（2026-10 新坑）

OpenAI 的 `Introducing GPT-6 in ChatGPT with Intelligent UI`（70 秒）是纯配乐 + 屏幕演示，
**没有任何旁白**。ASR 全文只有 78 个字符，内容就是 `Heat. Heat.` + `[music]` + `>>`。
`en-orig` 轨道同样如此，视频也**没有人工上传字幕**。

判断标准（聚合后先看一眼再决定要不要继续）：

- 总文本几十字符、有效单词 < 20、行数个位数 → 没有可配音内容；
- 此时**不要提交 bmx**：没有文本就没有配音，只会占服务端资源（且不去重）。

这类片子（产品发布短片、演示 reel、纯 BGM 视频）在 ASR 阶段就会暴露，早停比跑完再发现便宜。
