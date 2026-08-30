---
name: nows-keywordfilter
description: >-
  对文本进行敏感词/违禁词过滤与替换：调用内嵌在本 skill 的 bin/ 目录中的预编译、跨平台
  keywordfilter 可执行程序，词表已直接编译进各二进制内部，运行时不依赖任何外部文件。
  当用户要求对一段文本做敏感词过滤、违禁词替换、内容审核脱敏，或明确提到
  nows-keywordfilter 时使用。
disable-model-invocation: true
---

# nows-keywordfilter

封装 `keywordfilter` 命令行工具（Go 实现，Aho-Corasick 多模式匹配，词表内嵌）来做文本过滤。根据当前系统选择对应的二进制并执行，把替换后的文本返回给用户。

## 快速使用

1. 判断操作系统，从 `bin/` 目录选择对应二进制（路径相对本 skill 目录）：

   | 系统 | 二进制 |
   |------|--------|
   | macOS（Intel 或 Apple Silicon） | `bin/keywordfilter-darwin-universal` |
   | Linux（x86_64） | `bin/keywordfilter-linux-amd64` |
   | Windows（x86_64） | `bin/keywordfilter-windows-amd64.exe` |

   macOS/Linux 用 `uname -s` 判断（`Darwin` / `Linux`）；如果在 Windows 的
   PowerShell/cmd 环境或没有 `uname`，按 Windows 处理。

2. 确保二进制有可执行权限（仅 macOS/Linux，首次使用时执行一次）：

   ```bash
   chmod +x bin/keywordfilter-darwin-universal   # 或 bin/keywordfilter-linux-amd64
   ```

3. 直接执行该文件（**不要**用 `sh`/`bash 文件名` 去调用，它是编译好的二进制而不是脚本，那样会报
   "cannot execute binary file"）：

   ```bash
   ./bin/keywordfilter-darwin-universal -text "用户提供的文本" -replace "*"
   ```

4. 把返回的替换后文本输出给用户即可。

## 命令行参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-text` | 空 | 待过滤文本，直接内联传入；不传则从标准输入读取文本 |
| `-replace` | `*` | 替换字符串，按命中关键词的字符数重复填充 |
| `-stats` | `false` | 在 stderr 打印命中次数（不影响 stdout 的正文结果） |

行为说明：
- 英文关键词大小写不敏感匹配，中文按原样精确匹配。
- 多个关键词有前缀重叠时，按最长匹配处理（不会出现替换不干净、残留部分敏感字符的情况）。
- 结果始终输出到 stdout；没有 `-in`/`-out` 文件参数，长文本请用标准输入管道：

  ```bash
  printf '%s' "$待过滤文本" | ./bin/keywordfilter-darwin-universal -replace "*"
  ```

## 用法示例（占位符，非真实词表内容）

假设词表里包含关键词"敏感词甲"（3 个字），替换字符使用 `*`：

```bash
$ ./bin/keywordfilter-darwin-universal -text "这段话里出现了敏感词甲，其余内容正常" -stats
这段话里出现了***，其余内容正常
keywordfilter: 1 match(es) replaced
```
