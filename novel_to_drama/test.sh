#!/bin/bash
# 测试脚本 - 无需 API Key

echo "🎬 测试 Novel to Drama 项目"
echo "================================"
echo ""

# 测试数据加载
echo "📖 测试 1: 数据加载模块"
python3 scripts/data_loader.py examples/sample_novel
echo ""

# 测试降级方案（无 API）
echo "🎬 测试 2: 大纲生成（降级模式）"
python3 scripts/episode_mapper.py
echo ""

# 测试降级方案（无 API）
echo "🎬 测试 3: 剧本生成（降级模式）"
python3 scripts/script_generator.py
echo ""

# 测试导出模块
echo "💾 测试 4: 导出模块"
python3 scripts/exporter.py
echo ""

echo "✅ 所有测试完成！"
