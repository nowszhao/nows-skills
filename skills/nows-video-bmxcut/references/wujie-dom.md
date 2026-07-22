# Wujie Shadow DOM Reference for channels.weixin.qq.com

## Page Architecture

Video channel assistant uses **wujie micro-frontend framework**. The actual page content is nested inside:

```
document
  └── wujie-app (custom element)
        └── shadowRoot
              └── html
                    └── body  ← all form elements are here
```

## Accessing Elements

All `agent-browser eval` commands targeting the video channel form must navigate through this path:

```js
const wa = document.querySelector('wujie-app');
const body = wa.shadowRoot.querySelector('html').querySelector('body');
const element = body.querySelector('.target-class');
```

**CRITICAL:** `agent-browser click @ref` and `agent-browser upload` do NOT reach elements inside wujie shadow DOM. Use `eval` instead for clicks, and move file inputs to `document.body` first for uploads.

---

## Key Form Elements

### File Upload Input
```html
<input type="file" accept="video/mp4,video/x-m4v,video/*" multiple>
```
- Location: inside `.ant-upload` > `.ant-upload-drag`
- **Must be moved to document.body before upload:**
  ```js
  document.body.appendChild(body.querySelector('input[type=file]'));
  ```
- Then use: `agent-browser upload "input[type='file']" "/path/to/video.mp4"`

### Video Description (contenteditable)
```html
<div contenteditable="" data-placeholder="添加描述" class="input-editor"></div>
```
- `contenteditable=""` is equivalent to `contenteditable="true"`
- Use `keyboard.type` for each line, `press Enter` for newlines
- Format: `【{N}】{title}\n{description}\n{tags}`

### Short Title
```html
<input type="text" class="weui-desktop-form__input" placeholder="填写短标题有机会获得更多流量">
```
- Fastest method: JS direct value set + input event dispatch
  ```js
  t.value = 'Agentic知识图谱';
  t.dispatchEvent(new Event('input', {bubbles: true}));
  ```

### Location Dropdown
```
div.form-item-body
  └── div.post-position-wrap
        └── div.position-display
              └── div.position-display-wrap  ← click to open
                    └── span.location-name    ← "西安市" or selected location
```
- Options appear as: `不显示位置`, specific city names, etc.
- Click target: `body.querySelector('.post-position-wrap .position-display-wrap')`
- Select "不显示位置": find first element with `innerText.trim() === '不显示位置'` and `children.length < 5`

### Collection Dropdown
```
div.form-item-body
  └── div.post-album-display-wrap  ← click to open
        └── div.display-text       ← "选择合集" or selected collection
```
- Options appear with class `.option-item`
- Structure: `div.option-item > div.item > div.name`
- Click target: `body.querySelector('.post-album-display-wrap')`
- Select by matching innerText: `item.innerText.includes('吴恩达')` etc.

### Schedule Radio Buttons
```html
<input type="radio" value="0">  不定时 (default)
<input type="radio" value="1">  定时
```
- Click the second radio: `body.querySelectorAll('input[type=radio]')[1].click()`

### Publication Time (ant-design DatePicker)
```html
<input type="text" class="weui-desktop-form__input" placeholder="请选择发表时间">
```
- Focus this input to open the date picker overlay
- Inside the picker, find the time input:
  ```html
  <input placeholder="请选择时间">   ← ref will change each session
  ```
- Use `agent-browser snapshot | grep "textbox.*请选择时间"` to get the current ref
- Fill with desired time: `agent-browser fill <ref> "18:00"`
- **To close picker and commit time:** Click a safe label element (e.g. "视频标注") — NOT the page title "视频管理"

### Publish Button
```html
<button class="weui-desktop-btn weui-desktop-btn_primary">发表</button>
```
- Must click via eval due to wujie iframe cover:
  ```js
  const btn = Array.from(body.querySelectorAll('button')).find(b => b.innerText === '发表');
  btn.click();
  ```
- Save draft: button with innerText === '保存草稿'
- Phone preview: button with innerText === '手机预览'

---

## Common Obstacles & Recovery

### Login Modal ("账号已在其他设备登录")
```html
<div class="login-modal-wrap" data-v-e2103ac2="">
  <div class="login-content">
    <div class="modal-card">
      <div class="modal-header qrcode">
        <!-- close icon somewhere in here -->
      </div>
    </div>
  </div>
</div>
```
- This modal is at document level (NOT in wujie shadow DOM)
- Dismiss: `document.querySelector('.login-modal-wrap .close')?.click()` or find any close-related element
- The modal prevents clicking the Publish button

### Leave-Confirm Dialog ("将此次编辑保留？")
- Triggered by clicking the page title "视频管理" or any navigation link while form is filled
- Avoid clicking any navigation elements while in the post creation page
- If triggered, click "不保存" to dismiss (data will need re-entry)
- "保存" button does NOT actually save to drafts — it's misleading

### Upload Error ("网络出错，请重新上传")
- Cause: upload interrupted, session expired, or video file too large
- Solution: Reload page, re-enter all fields, re-upload
- Note: this sometimes appears after dismissing the login modal mid-session

---

## Page States and Transitions

### Home Page (Video List)
- URL: `/platform` or similar
- Shows: "发表视频" button, "最近视频" / "最近图文" tabs, scheduled video list
- Indicated by: body text containing "最近视频" and "最近图文"

### Post Creation Page
- URL: `/platform/post/create` (but SPA routing may show `/platform`)
- Shows: upload area, description editor, form fields
- Indicated by: body text containing "视频管理/发表动态"

### Draft Box
- URL: navigated from main menu "草稿箱"
- Shows: draft list (may be empty)

### Post List
- Reloads after successful publish
- Shows scheduled videos with "将于2026年0X月XX日 XX:00发表" entries

---

## Verification Patterns

After each publish, verify with:
```bash
agent-browser snapshot | grep "将于2026年"
```
Look for the new scheduled time entry. If not found within 3 seconds, check for login modal or error messages.

After completing all clips, verify the full schedule:
```bash
agent-browser snapshot | grep "将于2026年"  # should show all N clips
```
