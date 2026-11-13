# 插件目录规范

本项目同时是一个可安装插件。这里记录它遵循的目录约定，方便你自己照着写一个。

## 目录

```
<plugin-root>/
├── .codebuddy-plugin/
│   └── plugin.json        清单（必需）
├── .mcp.json              MCP 服务声明（插件含 MCP 服务时必需）
├── skills/
│   └── <skill-name>/
│       └── SKILL.md       技能入口（frontmatter + 说明）
├── bin/                   启动器（可选）
└── ...                    其余代码随意组织
```

## `.codebuddy-plugin/plugin.json`

```json
{
  "name": "logisim-mcp",
  "version": "1.1.0",
  "description": "一句话说明（会显示在插件列表里）",
  "description_en": "English one-liner (optional)",
  "author": { "name": "..." },
  "license": "MIT",
  "keywords": ["logisim", "eda"],
  "category": "eda",
  "skills": ["./skills/logisim-circuit-design"]
}
```

| 字段 | 必需 | 说明 |
|---|---|---|
| `name` | 是 | 插件标识，与市场条目、安装目录同名 |
| `version` | 是 | `x.y.z`。市场靠它判断"有更新" |
| `description` | 是 | 中文一句话，别超过两行 |
| `skills` | | 技能目录数组，相对插件根。技能名应与目录名一致 |
| `keywords` / `category` | | 用于市场检索 |
| `workbuddy.runtimeOwner` | | 让宿主用自己的运行时拉起 MCP（本项目用 `agent-cli`） |

## `.mcp.json`

```json
{
  "mcpServers": {
    "logisim": {
      "type": "stdio",
      "command": "python",
      "args": ["${CODEBUDDY_PLUGIN_ROOT}/server/server.py"],
      "cwd": "${CODEBUDDY_PLUGIN_ROOT}",
      "env": { "PYTHONUTF8": "1" },
      "defer_loading": false
    }
  }
}
```

可用占位符：

| 占位符 | 含义 |
|---|---|
| `${CODEBUDDY_PLUGIN_ROOT}` | 插件安装目录 |
| `${CODEBUDDY_PLUGIN_DATA}` | 该插件的数据目录（升级不覆盖，适合放数据库/日志/用户配置） |

`defer_loading: false` 表示工具在会话开始时就加载，而不是等模型主动请求。

> `command` 只写 `python` 时，依赖宿主进程的 PATH。稳妥做法：安装脚本把 `command`
> 改写成解释器绝对路径（本项目的 `tools/install.py` 默认就这么干），仓库里的 `.mcp.json` 保持可移植。

## `skills/<name>/SKILL.md`

```markdown
---
name: logisim-circuit-design
description: 什么时候该用这个技能（这段会被检索，写关键词）
---

# 标题

正文……
```

`name` 必须与目录名一致；`description` 是检索入口，把同义词和关键词都写进去（中英文都写更好）。

## 注册本地市场

插件市场本质上是一个目录，里面有清单：

```
<marketplace>/
├── .codebuddy-plugin/marketplace.json
└── plugins/<plugin-name>/          ← 插件本体
```

`marketplace.json`：

```json
{
  "name": "logisim-local",
  "description": "本地插件市场",
  "owner": { "name": "local" },
  "plugins": [
    { "name": "logisim-mcp", "version": "1.1.0",
      "source": "./plugins/logisim-mcp", "description": "..." }
  ]
}
```

再把它登记到宿主配置（`~/.workbuddy/plugins/known_marketplaces.json`）：

```json
{
  "logisim-local": {
    "manifestName": "logisim-local",
    "type": "directory",
    "source": { "source": "directory", "path": "<市场绝对路径>" },
    "installLocation": "<市场绝对路径>",
    "autoUpdate": false,
    "isBuiltIn": false
  }
}
```

之后在插件管理页就能看到并安装；`logisim` 这个 MCP 连接器还需要手动点一次 Trust。

本项目的 `tools/install.py` 把上面三步都做了，并且在改任何配置前留 `.bak-<时间戳>` 备份。

## 打包与发布的约定

- `dist/` 与 `*.zip` 不进仓库（`.gitignore`）；
- `.cmd` 必须 CRLF + 纯 ASCII（`.gitattributes` / `.editorconfig` 已约束）；
- 版本号三处一致：`plugin.json`、`server.py` 的兜底默认值、`CHANGELOG.md` 的小节标题。
  `tools/check_release.py` 会检查这一点，CI 也会跑。
