# 存储器案例：64KB ROM + 64KB RAM（32 位字长，字节编址）

3.2 存储器实验复盘。目标不是“能存数”，而是同时满足：

- ROM、RAM 各 **64KB**（16K × 32 位）；
- CPU 给 **16 位字节地址**，每个字节都有地址；
- 字长 32 位，一次访问 32 位；字访问按 4 字节对齐，内部用 `A[15:2]` 作字地址；
- 字访问、字节访问都必须在 **一个存储周期** 内完成；
- 模块化、自定义子电路外观、禁止隧道、RAM 异步读。

## 1. 总体结构

```
main
 ├─ rom64k        1 × 16K×32 ROM = 64KB
 └─ ram64k        4 × 16K×8 RAM 低位交叉 = 64KB
     ├─ bank0     存地址 4k+0 的字节
     ├─ bank1     存地址 4k+1 的字节
     ├─ bank2     存地址 4k+2 的字节
     ├─ bank3     存地址 4k+3 的字节
     ├─ 字节使能逻辑
     └─ 字/字节读选择
```

接口：

```
A[16]  DIN[32]  WE  BYTE  SEL  CLK  →  DOUT[32]

SEL=0 选 ROM，SEL=1 选 RAM
BYTE=0 字访问，BYTE=1 字节访问
```

## 2. 地址映射与字节序

| 信号 | 用途 |
|---|---|
| `A[15:2]` | 14 位字地址，同时送 ROM 和 4 个 RAM bank |
| `A[1:0]` | 字节通道，选择 bank / 字节 |
| `bank i` | 保存所有地址 `4k+i` 的字节 |

**低位交叉是 bank0 = LSB**：

```
字 0x11223344
  byte0 = 0x44  → bank0
  byte1 = 0x33  → bank1
  byte2 = 0x22  → bank2
  byte3 = 0x11  → bank3
```

写测试向量前先把这张表写清楚，否则很容易把“字节序反了”误判成 mux 接反。

## 3. 单周期读写规则

| SEL | BYTE | WE | 操作 |
|---|---|---|---|
| 0 | 0 | × | ROM 字读（异步） |
| 0 | 1 | × | ROM 字节读（低 8 位，高 24 位补 0） |
| 1 | 0 | 0 | RAM 字读（4 bank 并行） |
| 1 | 0 | 1 | RAM 字写（4 bank 同时写，CLK 上升沿） |
| 1 | 1 | 0 | RAM 字节读（只读选中 bank） |
| 1 | 1 | 1 | RAM 字节写（只写选中 bank，CLK 上升沿） |

字节使能：

```text
BE_i = ~BYTE | (A[1:0] == i)
WE_i = WE & SEL & BE_i
DIN_i = BYTE ? DIN[7:0] : DIN[8i+7 : 8i]
```

- 字写：4 个 bank 全部使能，一次写入 32 位；
- 字节写：只有 `A[1:0]` 选中的 bank 使能，其余 bank 保持原值；
- 读：RAM/ROM 都异步读，字节选择用组合 mux，不需要额外存储周期。

## 4. RAM/ROM 5.0 实测

### 16K×8 RAM

```xml
<comp lib="2" loc="(x,y)" name="RAM">
  <a name="addrWidth" val="14"/>
  <a name="dataWidth" val="8"/>
  <a name="enables" val="byte"/>
  <a name="type" val="volatile"/>
  <a name="trigger" val="rising"/>
  <a name="asyncread" val="true"/>
  <a name="databus" val="bibus"/>
  <a name="clearpin" val="false"/>
</comp>
```

- 体 `240×250`；
- 端口：`A(0,10) / D(0,90) / Q(240,90) / WE(0,50) / EN(0,60) / CLK(0,70)`；
- `EN` 是输出使能（OE），直接接 1；
- 写：`WE=1` 且 CLK 上升沿。

### 16K×32 ROM

```xml
<comp lib="2" loc="(x,y)" name="ROM">
  <a name="addrWidth" val="14"/>
  <a name="dataWidth" val="32"/>
  <a name="line" val="single"/>
  <a name="misaligned" val="false"/>
  <a name="contents" val="addr/data: 14 32&#10;11223344&#10;..."/>
</comp>
```

- 体 `240×220`；
- 端口：`A(0,10) / Q(240,60)`；
- `contents` 写成 `addr/data: <addrBits> <dataBits>` 后跟十六进制值列表；
- 只写前 N 个字时，其余地址按 0 填充；
- 不要写 `0x` 前缀。

## 5. 模块划分

### bank8
- 1 片 16K×8 RAM；
- 输入 `A[14] / D[8] / WE / CLK`，输出 `Q[8]`；
- `EN` 内部接常量 1；
- 外观约 180×170，名称牌 “RAM Bank 16Kx8”。

### rom64k
- 1 片 16K×32 ROM；
- 16 位地址用 8×2 拆分 + 7×2 合并得到 14 位字地址；
- 4:1 字节 mux + 8→32 零扩展 + 32 位字/字节 mux；
- 输入 `A[16] / BYTE`，输出 `DOUT[32]`。

### ram64k
- 4 个 `bank8`；
- 地址：`A[16]` → 8×2 拆分 → `b0` 作 lane，`b1..b7` → 7×2 合并成 `A[15:2]`；
- 数据：`DIN[32]` → 4×8 拆分，每个 bank 前放一个 8 位 2:1 mux；
- 写使能：2:4 译码器 + NOT + 4 OR + 4 AND；
- 读：4 个 `Q[8]` → 32 位合并 + 4:1 字节 mux + 零扩展 + 输出 mux；
- 输入 `A[16] / DIN[32] / WE / BYTE / CLK`，输出 `DOUT[32]`。

### main
- 输入引脚 → `rom64k` / `ram64k` → SEL 输出 mux → `DOUT`；
- `RAM_WE = WE & SEL`；
- 顶层连线控制在 20 段以内，复杂布线全部封装进子电路。

## 6. 外观

每个子电路都带自定义外观：

- 圆角框；
- 底部深色名称牌；
- 左侧输入标签、右侧输出标签；
- `<circ-port dir="in|out" pin="内部Pin坐标" x="外观坐标" y="外观坐标"/>`。

注意三处坐标必须一致：

1. 父电路里子电路实例的端口偏移；
2. `<appear><circ-port ... x y>`；
3. 子电路内部 `Pin` 的绝对坐标（`pin="x,y"`）。

父电路优先用 **20px 水平短桩** 进入端口，避免沿元件边缘走线。

## 7. 生成器要点

生成器用 `scripts/lib8.py` 的 `Board` 做 A* 正交布线，用 `scripts/route8.py` 做短接检查。
本案例的工厂函数包括：

- `add_ram()` / `add_rom()`；
- `add_split(fanout, incoming, facing)`；
- `add_mux(select, width)` / `add_decoder(select)` / `add_extender(in_w, out_w)`；
- `add_sub(loc, name, ports, w, h)`；
- `appear(...)`；
- `stub_left() / stub_right()`。

关键：**`add_pin()` 只建引脚，必须显式把 pin 坐标加入 net**。本案例先后漏了 `A` 和 `DIN`，
症状分别是地址全 `U`、写数据全 `U`（RAM 写不进、读回 `FF`）。

工程头必须补：

```xml
<lib desc="#Plexers" name="5"/>
```

否则 `Multiplexer/Decoder` 全部变成未识别元件，整机 `DOUT` 全 `U`，GUI 报「找不到库 5」。

## 8. 验证矩阵

| 测试 | 内容 | 结果 |
|---|---|---|
| ROM 字读 | `A=0x0000/0x0004` | 通过 |
| ROM 字节读 | `A=0x0000..0x0003/0x0007` | 通过 |
| RAM 字写读 | `0x0100 ← 0x11223344` | 通过 |
| RAM 字节写读 | `0x0101/0x0102/0x0103` 分别写 | 通过 |
| 相邻字节保护 | 写一个字节，其余 3 字节不变 | 通过 |
| bank 交叉 | `0x0104 ← 0x55667788` | 通过 |
| SEL 隔离 | 同地址 ROM/RAM 互不影响 | 通过 |
| 单 bank | `bank8` 写时序 | 7/7 |
| ram64k | 字/字节读写 16 行 | 16/16 |
| main | 全量 37 行 | 37/37 |

测试向量列：

```text
A[16] DIN[32] WE BYTE SEL CLK DOUT[32] <set> <seq>
```

要点：

- 同一 `<set>`、递增 `<seq>`，状态跨行保留（含子电路实例）；
- CLK 用 0→1 两行制造上升沿；
- 写行期望值用 `<DC>`；
- 必须确认「通过数 == 数据行数」，防止列名不匹配被静默跳过。

## 9. 坑点速查（I 组）

| # | 坑 | 症状 | 修法 |
|---|---|---|---|
| I1 | 缺 `#Plexers` | 全 `U`，GUI 报找不到库 5 | 工程头补 lib 5 |
| I2 | Pin 未入网 | 地址/数据 `U`，RAM 写不进 | 每个 Pin 至少进一条 net |
| I3 | `connect()` 自检盲区 | 断线也能“通过” | 记录端点 + 并查集 |
| I4 | 字节序按大端 | 字节读“错位” | bank0 = LSB |
| I5 | `.circ.autosave` | `-t stats` 加载失败 | 关 GUI、删 autosave |
| I6 | `circ_audit` partial | 正常连接报 dangling | 以 `-w` 功能向量为准 |
| I7 | 手写调试 `.circ` | Logisim 卡死/弹窗 | 调试电路也走生成器 |
| I8 | preview 截外观 | main 只有空框 | GUI + 窗口截图 |
| I9 | RAM/ROM 端口照搬 | 线接不上/宽度错 | 用 `circ_probe` 实测 |
| I10 | Splitter 想拆 2+14 | 拆不出来 | 8×2 + 7×2 |
| I11 | ROM contents 格式 | 读回全 0 | `addr/data: 14 32` + hex 列表 |
| I12 | 向量列名不匹配 | 静默跳过/假通过 | 通过数 == 数据行数 |

## 10. 排查决策树

```
DOUT 全 U
  → 工程头有没有 #Plexers？
  → 每个输入 Pin 是否进了某条 net？
  → 子电路外观端口与父电路导线坐标是否一致？

RAM 写不进 / 读回 FF
  → 先单 bank 直连测（A/D/WE/CLK）
  → 再测数据通路（DIN → 分线 → mux）
  → 再测控制逻辑（BE/WE）
  → 最后测多 bank 扇出

字节读错位
  → 先确认 bank 映射和字节序
  → 再怀疑 4:1 mux 的 select 顺序

-t stats 加载失败但 -w 能跑
  → 删 .circ.autosave

circ_audit 报 dangling 但 -w 能跑
  → 看结论是否 partial；RAM/ROM/Bit Extender 不支持
```

## 11. 交付检查清单

- [ ] 工程头含 `#Plexers`；
- [ ] 所有声明的 Pin 都进了 net；
- [ ] 4 个 bank 的 A/D/WE/CLK 都是水平短桩进入；
- [ ] 字节使能 `BE_i = ~BYTE | (A[1:0]==i)`；
- [ ] 字写 4 bank 并行，字节写只写一个 bank；
- [ ] ROM contents 格式正确；
- [ ] `-t stats` 退出码 0；
- [ ] `-w` 全量向量通过数 == 数据行数；
- [ ] 子电路外观 `circ-port` 与内部 Pin 一致；
- [ ] 无隧道、无 `.autosave`、无调试文件混入交付目录。
