# bytepub

将 ByteByteGo 课程内容抓取并转换为 EPUB 电子书，支持图片、公式、表格的完整保留。

## 安装

```bash
uv sync
uv run playwright install chromium
```

## 使用

### 测试单页

```bash
uv run bytepub test "https://bytebytego.com/courses/xxx/chapter-slug" --no-auth
```

运行后在 `output/test/` 下生成：

```
output/test/
├── cleaned.html    # 清洗后的 HTML（可直接浏览器打开预览）
├── test.epub       # 生成的 EPUB 电子书
├── assets/         # 下载的图片资源
└── cache/          # HTML 缓存（再次运行时跳过下载）
```

完整样例见 [`examples/`](examples/) 目录。

### 抓取整门课程

```bash
# 免费章节
uv run bytepub scrape "https://bytebytego.com/courses/xxx/chapter-slug" --no-auth

# 需要登录（首次打开浏览器登录，之后自动复用 session）
uv run bytepub scrape "https://bytebytego.com/courses/xxx/chapter-slug"
```

### 常用选项

| 选项 | 说明 |
|------|------|
| `--no-auth` | 跳过登录，仅抓取免费内容 |
| `-o output` | 输出目录（默认 output） |
| `--format epub/markdown/all` | 输出格式：`epub`（默认）、`markdown`、`all`（同时生成两种） |
| `--refresh 1 3` | 重新抓取指定章节，不加编号则刷新全部 |
| `--delay-min 3 --delay-max 8` | 页面间隔秒数（默认 3-8 秒） |
| `--cover image.png` | 自定义封面图 |

## 功能

- **图片处理**：自动下载、检测真实格式、WebP/SVG 转 PNG、路径重写
- **表格样式**：自动添加边框和表头样式
- **本地缓存**：HTML、图片、章节列表缓存到本地，支持断点续抓
- **自动登录复用**：浏览器数据持久化到 `output/.browser-data/`，首次运行登录后，后续自动复用 session（Firebase refresh token 自动续期，无需重复登录）
- **章节目录**：h1 带序号、子标题嵌套目录（优先 h2，无 h2 时自动使用 h3）、TOC 自动去除列表编号
- **章节发现**：自动从侧边栏识别课程全部章节

## 免责声明

本项目仅供个人学习使用，目的是将已购买的课程内容导出至 Kindle 等设备离线阅读，请勿用于任何非法用途。课程内容版权归原作者所有，请尊重知识产权。
