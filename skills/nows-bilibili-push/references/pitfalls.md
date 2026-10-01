# B站投稿 UI 坑位清单（实战踩坑记录）

本文件记录 B站创作中心投稿页的真实 DOM 结构与反直觉行为。
**改动 `scripts/bilibili_push.py` 前请先读这里。**

---

## 1. 不要用 agent-browser 做上传

agent-browser 启动 Chrome 时会强制加 `--proxy-server=http://127.0.0.1:61468`（内置抓包代理）。
上传 100MB+ 文件时，代理转发会打满 Node 守护进程的事件循环，导致所有 CDP 命令
（`get url` / `eval` / `screenshot`）**永久挂起**（实测 100 秒超时仍无响应），且没有关闭开关。

→ 直接用 Playwright，不经过该代理。

Chrome 可执行文件优先用 agent-browser 已下载的：
`~/.agent-browser/browsers/chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`
（只是借用二进制，不走它的代理）

---

## 2. 视频上传：必须用 file input 索引 0

页面有 3 个 `input[type=file]`：

| 索引 | accept | name | 说明 |
|---|---|---|---|
| 0 | `.mp4,.flv,...` | （空） | 父元素 `div.bcc-upload-wrapper`，**真正接收视频** |
| 1 | `.mp4,.flv,...` | `buploader` | **隐藏诱饵**，父元素无文字，往它 set 文件毫无反应 |
| 2 | `.txt` | `buploader` | 字幕 |

```python
page.locator("input[type=file]").nth(0).set_input_files(video)
```

踩坑表现：往索引 1 塞文件，等 190 秒仍是「进度=None、无标题框」，毫无报错。

---

## 3. 创作声明：必填，缺失会"静默失败"

表单共 9 个区块：封面 / 标题 / **创作声明** / 分区 / 标签 / 简介 / 定时发布 / 加入合集 / 商业推广。

**不选创作声明时，点「立即投稿」没有任何提示，稿件也不会进列表**——日志看起来是成功的，实际全没提交。

选「内容无需标注」= `copyright 3`，与转载/自制相比不需要额外信息（选"转载"会要求填来源）。
分区保持页面默认（tid=27），不要改。

---

## 4. 简介（Quill）：可见的是第 1 个，且预置了示例文字

页面有 2 个 `.ql-editor`：

- **索引 0**：`ql-editor`，**可见**，里面预置了如「日常生活英语，每天听」的示例文字
- 索引 1：`ql-editor ql-blank`，**不可见**（`offsetParent` 为 null）

→ 必须操作**索引 0**，且先 `Control+a` 全选清掉残留文字，再 `keyboard.type()`。

无效的方式：`execCommand('insertText')`、`page.keyboard.insert_text()` 都写不进去（实测字数=0）。
有效：真实 click + Ctrl+A + `keyboard.type(desc, delay=1)`。

---

## 5. Vue 组件不响应 `el.click()`

B站 的时间单元格、下拉选项、提交按钮等，单纯 `element.click()` **不会触发 Vue 更新**
（实测返回 clicked 但值不变）。

必须派发完整鼠标事件序列，且对**子元素和自身各来一遍**：

```js
const fire = (el) => ['mouseover','mousedown','mouseup','click'].forEach(t =>
  el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
fire(it.children.length ? it.children[0] : it);
fire(it);
```

---

## 6. 定时发布时间：两个细节

时间面板结构：`.time-picker-panel-select-wrp` 两列——**列0 = 小时(00-23)，列1 = 分钟(00-55 步长5)**。

- **小时和分钟要分两次 `evaluate` 触发**。合并成一次调用会失效（实测全不生效）。
- **选完后不要点页面别处关面板**，点击外部会取消选择（实测改后仍显示原值）。直接保存即可。

日期：`.date-picker-body-item` 单元格，选 `.date-show` 显示的当前值；
被禁用（超出 15 天）的带 `date-item-disabled`，需跳过。

---

## 7. 封面：双比例 + checkbox

打开方式：用鼠标事件点 `.edit-text`（"封面设置"）。普通 `.click()` 在弹窗场景下会超时。

弹窗内 `input[type=file][accept*="image/png"]` 用于上传自定义封面。

**「双比例同步改动」是 checkbox，不是 switch**：

```html
<div class="sync ratio_16_9 sync-checkbox-wrapper">
  <span>双比例同步改动</span>
  <label class="sync-checkbox bcc-checkbox">
    <input type="checkbox" value="false">
  </label>
</div>
```

→ 要点击 `.sync-checkbox` label 才能勾选。若没勾，16:9 那张仍是 B站 自动截的视频帧。

---

## 8. 编辑已投稿稿件

URL 必须带 `type=edit`，只给 `?aid=` 不会加载表单：

```
https://member.bilibili.com/platform/upload/video/frame?type=edit&aid=<aid>
```

---

## 9. 校验：用 API 而不是解析 DOM

```
GET /x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=30&tid=0&order=pubdate
```

在已登录页面上下文里 `fetch(..., {credentials:'include'})` 即可。

- 定时时间在 **`Archive.dtime`**（注意在 Archive 内层，外层 `dtime` 是 null）
- `Archive.cover` 是 **16:9 个人空间封面**
- `copyright` 3 = 内容无需标注；`tid` = 分区

内容管理页 DOM 解析极不可靠（列表行选择器经常匹配不到），一律走 API。

---

## 10. 排查清单：点了提交但稿件没出现

按此顺序检查：

1. **创作声明选了吗？**（最常见，静默失败）
2. 定时时间是否在 5 分钟 ~ 15 天之间？
3. 标题是否超过 80 字？
4. 分区是否为默认值（未改动）？
5. 用 API 查 `Archive.dtime` 确认，而不是看界面按钮文案
   （按钮在开启定时后**仍可能显示"立即投稿"**，不代表没生效）

---

## 11. 删除稿件需要验证码

`POST /x/web/archive/delete` 返回 `{"code":340022,"message":"验证码错误"}`，
界面删除弹窗也是"验证并删除此视频"。**自动化删不掉，只能手动处理。**

→ 调试阶段务必用 `--no-submit`，或拿小测试视频时避免点提交。
