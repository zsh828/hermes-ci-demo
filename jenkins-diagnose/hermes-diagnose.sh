#!/bin/bash
#==============================================================================
# 脚本名称: hermes-diagnose.sh
# 描述: Jenkins 构建失败自动诊断脚本
# 位置: 应被挂载到 Jenkins 容器内的项目目录中
# 环境变量: JOB_NAME, BUILD_NUMBER (由 Jenkins 自动注入)
# 依赖: curl, python3
#==============================================================================

set -euo pipefail

#---------------- 配置区 ----------------
JENKINS_URL="http://localhost:8080"
# Jenkins Credentials ID (通过 withCredentials 注入)
# 如果在脚本内硬编码 Token，请替换以下变量
JENKINS_TOKEN="${JENKINS_TOKEN:-}"
#---------------------------------------


# 打印诊断开始信息
echo "=========================================="
echo "Hermes CI 自动诊断报告"
echo "=========================================="
echo "Job: ${JOB_NAME:-未设置}"
echo "构建号: ${BUILD_NUMBER:-未设置}"
echo "诊断时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 检查必要参数
if [[ -z "${JOB_NAME:-}" ]] || [[ -z "${BUILD_NUMBER:-}" ]]; then
    echo "[错误] 缺少必要环境变量 JOB_NAME 或 BUILD_NUMBER"
    echo "本脚本应由 Jenkins Pipeline 自动调用，请在 post failure 块中配置"
    exit 1
fi

# 获取构建日志
LOG_URL="${JENKINS_URL}/job/${JOB_NAME}/${BUILD_NUMBER}/consoleText"
echo ""
echo "[1/3] 正在获取构建日志..."
echo "URL: ${LOG_URL}"

BUILD_LOG=$(curl -s -u "${JENKINS_USER}:${JENKINS_TOKEN}" "${LOG_URL}")

if [[ -z "${BUILD_LOG}" ]]; then
    echo "[错误] 无法获取构建日志，请检查 Jenkins 认证和网络连接"
    exit 1
fi

echo "[日志获取成功] 长度: ${#BUILD_LOG} 字符"

# 调用诊断技能分析
echo ""
echo "[2/3] 正在执行日志分析..."
echo "------------------------------------------"

# 通过 hermes-bridge HTTP 接口调用诊断
DIAGNOSE_URL="http://localhost:18992/diagnose"

RESPONSE=$(curl -s -X POST "${DIAGNOSE_URL}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg log "$BUILD_LOG" --arg job "$JOB_NAME" --arg build "$BUILD_NUMBER" \
        '{log: $log, job_name: $job, build_number: $build}')")

if [[ -z "$RESPONSE" ]]; then
    echo "[错误] 诊断服务无响应，请检查 hermes-bridge 是否运行"
    exit 1
fi

echo "$RESPONSE"
echo "------------------------------------------"
echo ""

# 输出诊断完成信息
echo "[3/3] 诊断完成"
echo ""
echo "=========================================="
echo "如需手动查看完整日志，请访问:"
echo "${JENKINS_URL}/job/${JOB_NAME}/${BUILD_NUMBER}/console"
echo "=========================================="