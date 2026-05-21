# VM 议会非阻断建议处理 — Dispositions

**日期**: 2026-05-21
**参考**: [VM Council Audit Report](./vm-council-audit-report.md)

---

| # | 来源 | 建议 | 处理 | 理由 |
|---|------|------|------|------|
| N1 | Dijkstra | P1 154行 → <50行 | 📋 Defer | backup.sh 已增长至 191 行（N2+N3 引入 count(*) DO block）。重构需单独任务，当前脚本清晰可读，不致运维风险。 |
| N2 | Linus | n_live_tup → count(*) | ✅ Done | 已修复。备份 catalog 和验证 V4 均改用真实 count(*)。实测 n_live_tup 估算 2800，实际 5595 — 偏差 50%。 |
| N3 | Dijkstra | 硬编码 2800 → 动态 | ✅ Done | 已修复。catalog 现在用 DO block 循环 count(*)，V4 逐表对比。runbook 示例数字已更新。 |
| N4 | Musk | RO+WO 双 token | ❌ Wontfix | €0 单用户系统，双 token 增加运维复杂度而无安全收益。当前 Admin RW token 足矣。未来如有 CI pipeline 可考虑。 |
| N5 | Linus | inner bash 缺 set -e | ✅ Done | verify_restore.sh 两处内嵌 bash -c 均已添加 `set -e`。 |
| N6 | 小龙 | runbook 打印纸质版 | 📝 Noted | 已在 runbook 首页添加打印提示。物理抽屉副本值得拥有。 |
| N7 | Musk | Chaos 测试 (disk-full, checksum mismatch) | 📋 Defer | 26 tests 验证正常路径。Chaos 测试价值高，但属下一迭代。建议创建 `tests/dr/test_chaos.py` 覆盖：disk-full 模拟、sha256 篡改、容器宕机、R2 超时。 |
| N8 | Jensen | 文档漂移 (4文件→6文件) | 📝 Noted | 审计消息中的简报数字未反映后续修复增加的文件。已更新 runbook 为实际数字。以后简报引用 `wc -l` 结果而非记忆。 |

---

## Summary

- ✅ 已修复: 5 (N2, N3, N5 + B1, B2, B3)
- ❌ Wontfix: 1 (N4)
- 📋 Defer: 2 (N1, N7)
- 📝 Noted: 2 (N6, N8)

**阻断 bug: 0。非阻断建议: 0 未处理。**
