# VM 议会审计报告 — DR 交付物 (P1-P5)

**日期**: 2026-05-21
**被审**: 本地团队 P1-P5 DR 实施 (16 files, 1846 lines)
**审计方**: VM 议会 (Musk/Dijkstra/Linus/Jensen/雪峰/小龙)

---

## 逐项投票

| # | 交付物 | Musk | Dijkstra | Linus | Jensen | 雪峰 | 小龙 | 结果 |
|---|--------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| P1 | backup.sh (154行) | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | 5/1 PASS |
| P2 | setup-r2.sh (81行) | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | 4/2 PASS |
| P3 | verify_restore.sh (147行) | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | 6/0 PASS |
| P4 | tests/dr/ (26 cases) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 6/0 PASS |
| P5 | runbook (5 scenarios) | ✅ | ✅ | ❌ | ✅ | ⚠️ | ✅ | 4/2 PASS |
| DOCS | bilingual MD+HTML | — | ✅ | ✅ | ✅ | — | — | PASS |
| BUDGET | €12K→€1,816→€0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 6/0 PASS |

---

## 阻断级 Bug (3个, 必须修)

### B1: P2 — rclone 静默跳过 (Musk, Dijkstra)

```bash
# 当前代码
if ! command -v rclone &>/dev/null; then
    echo "rclone not installed. Skipping cloud sync."
    exit 0  # ← 静默成功，备份悄悄没上传
fi
```

**修复**: `exit 1` 替代 `exit 0`。rclone 未安装 = 备份失败，不是可选的。

### B2: P5 S2 — 磁盘全毁恢复路径嵌套 (雪峰)

```
S2 Step 4: rclone sync r2:... /backups/pg/latest/
  → 产生 /backups/pg/latest/20260521_030000/pathfinder_*.dump

S2 Step 6: ls /backups/pg/latest/pathfinder_*.dump
  → 找不到 (文件在更深一层)
```

**修复**: sync 到 `/backups/pg/` 根目录，然后用 `latest` 软链接找文件。

### B3: P5 S5 — runbook 引用不存在的 CLI 参数 (Linus)

```
S5 Step 2: verify_restore.sh --backup-dir /backups/pg/20260520
```

`verify_restore.sh` 不接受 `--backup-dir` 参数。

**修复**: 让脚本接受可选参数 `$1`，或文档改成 symlink 方式。

---

## 非阻断建议

| # | 来源 | 内容 |
|---|------|------|
| N1 | Dijkstra | P1 154行 → 应重构到 <50行 |
| N2 | Linus | P3 V4 用 `n_live_tup` (统计估算) 而非 `count(*)` — 2800行无影响，百万行会炸 |
| N3 | Dijkstra | P3 V4 硬编码 2800 → 应查询 live catalog 或用容差 |
| N4 | Musk | P2 单 RW token → 应为 RO+WO 双 token 分离 |
| N5 | Linus | P3 inner bash 缺 `set -e` |
| N6 | 小龙 | P5 runbook 打印纸质版放抽屉 |
| N7 | Musk | 26 tests 0 fail = 缺 chaos 测试 (disk-full, checksum mismatch, timeout) |
| N8 | Jensen | 简报称 4文件426行，实际 6文件500行 — 文档漂移 |

---

## 结论

**P1/P3/P4 可上生产。P2 + P5 修3个 bug 后重新审计。**

本地团队交付质量高 — 四层验证架构正确，bash 选型恰当，runbook 场景完整。16文件1846行，克制、安静、零运营成本。

**— VM 议会 6/6 附议, 陛下已阅**
