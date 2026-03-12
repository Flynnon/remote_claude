#!/bin/bash
# Docker 测试主脚本
# 验证 npm 包在不同环境下的完整性和功能可用性

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 统计变量
PASSED=0
FAILED=0
TEST_REPORT=""

# 结果目录
RESULTS_DIR="/home/testuser/test-results"
mkdir -p "$RESULTS_DIR"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASSED=$((PASSED + 1))
    report "$1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILED=$((FAILED + 1))
    report "$1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    report "⚠ $1"
}

report() {
    TEST_REPORT+="$1\n"
}

# 打印函数
print_header() {
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 步骤 1：环境检查
check_environment() {
    print_header "步骤 1：环境检查"

    # Python 版本
    if python3 --version &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        log_success "Python: $PYTHON_VERSION"
        report "✓ Python: $PYTHON_VERSION"
    else
        log_error "未找到 Python"
        report "✗ Python: 未找到"
        return 1
    fi

    # uv 版本
    if uv --version &> /dev/null; then
        UV_VERSION=$(uv --version)
        log_success "uv: $UV_VERSION"
        report "✓ uv: $UV_VERSION"
    else
        log_error "未找到 uv"
        report "✗ uv: 未找到"
        return 1
    fi

    # tmux 版本
    if tmux -V &> /dev/null; then
        TMUX_VERSION=$(tmux -V)
        log_success "tmux: $TMUX_VERSION"
        report "✓ tmux: $TMUX_VERSION"
    else
        log_error "未找到 tmux"
        report "✗ tmux: 未找到"
        return 1
    fi

    # Node.js 版本
    if node --version &> /dev/null; then
        NODE_VERSION=$(node --version)
        log_success "Node.js: $NODE_VERSION"
        report "✓ Node.js: $NODE_VERSION"
    else
        log_error "未找到 Node.js"
        report "✗ Node.js: 未找到"
        return 1
    fi

    # npm 版本
    if npm --version &> /dev/null; then
        NPM_VERSION=$(npm --version)
        log_success "npm: $NPM_VERSION"
        report "✓ npm: $NPM_VERSION"
    else
        log_error "未找到 npm"
        report "✗ npm: 未找到"
        return 1
    fi

    # Claude CLI（可选）
    if claude --version &> /dev/null; then
        log_success "Claude CLI: $(claude --version 2>&1 | head -1)"
        report "✓ Claude CLI: $(claude --version 2>&1 | head -1)"
    else
        log_warning "Claude CLI: 未找到（非必需，npm 包不依赖）"
        report "⚠ Claude CLI: 未找到（非必需）"
    fi
}

# 步骤 2：打包 npm 包
pack_npm_package() {
    print_header "步骤 2：打包 npm 包"

    # 复制项目到可写目录（因为 /project 是只读挂载）
    local temp_project="/tmp/project-copy"
    rm -rf "$temp_project"
    cp -r /project "$temp_project"
    cd "$temp_project"

    if npm pack > "$RESULTS_DIR/pack.log" 2>&1; then
        PACK_FILE=$(ls -t remote-claude-*.tgz 2>/dev/null | head -1)
        VERSION=$(echo "$PACK_FILE" | sed 's/remote-claude-\(.*\)\.tgz/\1/')
        log_success "npm 包打包成功: $PACK_FILE"
        log_info "版本: $VERSION"
        report "✓ npm 包打包成功: $PACK_FILE (版本: $VERSION)"
        echo "$VERSION" > "$RESULTS_DIR/version.txt"
        mv "$PACK_FILE" /tmp/
    else
        log_error "npm pack 失败"
        report "✗ npm pack 失败"
        cat "$RESULTS_DIR/pack.log"
        return 1
    fi
}

# 步骤 3：模拟用户安装
simulate_install() {
    print_header "步骤 3：模拟用户安装"

    local pack_file="$1"

    # 创建临时安装目录
    local install_dir="/home/testuser/test-npm-install"
    rm -rf "$install_dir"
    mkdir -p "$install_dir"
    cd "$install_dir"

    log_info "在临时目录安装 npm 包..."

    if npm install "$pack_file" > "$RESULTS_DIR/npm_install.log" 2>&1; then
        log_success "npm install 成功"
        report "✓ npm install 成功"
    else
        log_error "npm install 失败"
        report "✗ npm install 失败"
        cat "$RESULTS_DIR/npm_install.log"
        return 1
    fi

    # 将安装目录路径写入文件（供后续步骤使用）
    echo "$install_dir" > "$RESULTS_DIR/install_dir.txt"
}

# 步骤 4：验证 postinstall 执行
verify_postinstall() {
    print_header "步骤 4：验证 postinstall 执行"

    local install_dir="$1"
    cd "$install_dir/node_modules/remote-claude"

    # 验证 .venv 目录
    if [ -d ".venv" ]; then
        log_success ".venv 虚拟环境已创建"
        report "✓ .venv 虚拟环境已创建"
    else
        log_error ".venv 虚拟环境未创建"
        report "✗ .venv 虚拟环境未创建"
        return 1
    fi

    # 验证 pyproject.toml 存在
    if [ -f "pyproject.toml" ]; then
        log_success "pyproject.toml 存在"
        report "✓ pyproject.toml 存在"
    else
        log_error "pyproject.toml 不存在"
        report "✗ pyproject.toml 不存在"
        return 1
    fi

    # 检查 Python 依赖（使用 .venv 中的 Python）
    log_info "检查 Python 依赖安装..."

    if .venv/bin/python -c "import lark_oapi" 2>/dev/null; then
        log_success "lark-oapi 已安装"
        report "✓ lark-oapi 已安装"
    else
        log_error "lark-oapi 未安装"
        report "✗ lark-oapi 未安装"
        return 1
    fi

    if .venv/bin/python -c "import dotenv" 2>/dev/null; then
        log_success "python-dotenv 已安装"
        report "✓ python-dotenv 已安装"
    else
        log_error "python-dotenv 未安装"
        report "✗ python-dotenv 未安装"
        return 1
    fi

    if .venv/bin/python -c "import pyte" 2>/dev/null; then
        log_success "pyte 已安装"
        report "✓ pyte 已安装"
    else
        log_error "pyte 未安装"
        report "✗ pyte 未安装"
        return 1
    fi
}

# 步骤 5：测试基本命令
test_basic_commands() {
    print_header "步骤 5：测试基本命令"

    local install_dir="$1"
    cd "$install_dir/node_modules/remote-claude"

    # 测试 remote-claude --help
    log_info "测试 remote-claude --help..."
    if uv run python3 remote_claude.py --help > "$RESULTS_DIR/cmd_help.log" 2>&1; then
        if grep -q "双端共享 Claude CLI 工具" "$RESULTS_DIR/cmd_help.log"; then
            log_success "remote-claude --help 输出正确"
            report "✓ remote-claude --help 输出正确"
        else
            log_error "remote-claude --help 输出异常"
            report "✗ remote-claude --help 输出异常"
            return 1
        fi
    else
        log_error "remote-claude --help 执行失败"
        report "✗ remote-claude --help 执行失败"
        return 1
    fi

    # 测试 remote-claude list
    log_info "测试 remote-claude list..."
    if uv run python3 remote_claude.py list > "$RESULTS_DIR/cmd_list.log" 2>&1; then
        log_success "remote-claude list 执行成功"
        report "✓ remote-claude list 执行成功"
    else
        log_error "remote-claude list 执行失败"
        report "✗ remote-claude list 执行失败"
        return 1
    fi

    # 检查 cla 脚本语法
    log_info "检查 cla 脚本语法..."
    if bash -n "$install_dir/../bin/cla" 2>/dev/null; then
        log_success "bin/cla 脚本语法正确"
        report "✓ bin/cla 脚本语法正确"
    else
        log_error "bin/cla 脚本语法错误"
        report "✗ bin/cla 脚本语法错误"
        return 1
    fi

    # 验证 cla 脚本中的关键逻辑
    log_info "验证 cla 脚本中的关键逻辑..."

    if grep -q "uv run" "$install_dir/../bin/cla"; then
        log_success "cla 脚本包含 uv run"
        report "✓ cla 脚本包含 uv run"
    else
        log_error "cla 脚本缺少 uv run"
        report "✗ cla 脚本缺少 uv run"
        return 1
    fi

    if grep -q "remote_claude.py" "$install_dir/../bin/cla"; then
        log_success "cla 脚本包含 remote_claude.py"
        report "✓ cla 脚本包含 remote_claude.py"
    else
        log_error "cla 脚本缺少 remote_claude.py"
        report "✗ cla 脚本缺少 remote_claude.py"
        return 1
    fi

    if grep -q "lark start" "$install_dir/../bin/cla"; then
        log_success "cla 脚本包含 lark start"
        report "✓ cla 脚本包含 lark start"
    else
        log_error "cla 脚本缺少 lark start"
        report "✗ cla 脚本缺少 lark start"
        return 1
    fi
}

# 步骤 6：文件完整性检查
check_file_integrity() {
    print_header "步骤 6：文件完整性检查"

    local install_dir="$1"
    cd "$install_dir/node_modules/remote-claude"

    # 关键文件列表
    local critical_files=(
        "remote_claude.py"
        "server/server.py"
        "client/client.py"
        "utils/protocol.py"
        "lark_client/main.py"
        "init.sh"
        "pyproject.toml"
        ".env.example"
    )

    local missing_files=()
    for file in "${critical_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "文件存在: $file"
            report "✓ 文件存在: $file"
        else
            log_error "文件缺失: $file"
            report "✗ 文件缺失: $file"
            missing_files+=("$file")
        fi
    done

    if [ ${#missing_files[@]} -eq 0 ]; then
        log_success "所有关键文件检查通过"
        report "✓ 所有关键文件检查通过"
        return 0
    else
        log_error "缺失 ${#missing_files[@]} 个关键文件"
        report "✗ 缺失 ${#missing_files[@]} 个关键文件"
        return 1
    fi
}

# 步骤 7：生成测试报告
generate_report() {
    print_header "步骤 7：生成测试报告"

    local report_file="$RESULTS_DIR/test_report.md"

    cat > "$report_file" << EOF
# Docker 测试报告

**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')
**测试版本**: $(cat "$RESULTS_DIR/version.txt" 2>/dev/null || echo "unknown")

## 测试摘要

- 通过: $PASSED
- 失败: $FAILED
- 总计: $((PASSED + FAILED))

**总体结果**: $([ $FAILED -eq 0 ] && echo "✅ 通过" || echo "❌ 失败")

## 环境信息

- 操作系统: $(uname -a)
- Python: $(python3 --version)
- Node.js: $(node --version)
- npm: $(npm --version)
- uv: $(uv --version)
- tmux: $(tmux -V)

## 测试详情

$TEST_REPORT

## 测试日志

- npm 打包: \`pack.log\`
- npm 安装: \`npm_install.log\`

## 诊断信息

如测试失败，请运行 \`docker/scripts/docker-diagnose.sh\` 收集诊断信息。

---

*此报告由 Docker 测试脚本自动生成*
EOF

    log_success "测试报告已生成: $report_file"
    report "✓ 测试报告已生成: $report_file"
}

# 步骤 8：清理
cleanup() {
    print_header "步骤 8：清理"

    # 不停止容器和会话，让容器保持运行状态
    log_info "保持容器运行状态（Docker 模式下不自动退出）"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}容器保持运行状态（Docker 模式下不自动退出）${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${GREEN}进入容器的命令：${NC}"
    echo -e "  docker exec -it 907063146e1ad43d53cddc51c905eb0c09ae6abce3c7d76c16d3422c66c643s /bin/bash${NC}"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}查看测试报告：${NC}"
    echo -e "  docker exec 907063146e1ad43d53cddc51c905eb0c09ae6abce3c7d76c16d3422c66c643s /bin/bash cat /home/testuser/test-results/test_report.md${NC}"
    echo ""
    echo -e "${YELLOW}查看安装目录结构：${NC}"
    echo -e "  docker exec 907063146e1ad43d53cddc51c905eb0c09ae6abce3c7d76c16d3422c66c643s /bin/bash ls -la /home/testuser/test-npm-install/node_modules/remote-claude/${NC}"
    echo ""
    echo -e "${YELLOW}手动运行测试：${NC}"
    echo -e "  docker exec 907063146e1ad43d53cddc51c905eb0c09ae6abce3c7d76c16d3422c66c643s /bin/bash -c 'cd /project && docker/scripts/docker-test.sh'${NC}"
    echo ""
    echo -e "${YELLOW}停止容器：${NC}"
    echo -e "  docker stop 907063146e1ad43d53cddc51c905eb0c09ae6abce3c7d76c16d3422c66c643s${NC}"
    echo ""

    log_success "清理完成（容器保持运行状态）"
}

# 输出最终结果
print_results() {
    print_header "测试完成"
    log_info "通过: $PASSED, 失败: $FAILED"

    if [ $FAILED -eq 0 ]; then
        log_success "所有测试通过！✅"
    else
        log_error "存在 $FAILED 个失败测试 ❌"
    fi
}

# 主流程
main() {
    log_info "Docker 测试开始..."

    # 步骤 1：环境检查
    if ! check_environment; then
        log_error "环境检查失败，终止测试"
        exit 1
    fi

    # 步骤 2：打包 npm 包
    if ! pack_npm_package; then
        log_error "npm 包打包失败，终止测试"
        exit 1
    fi

    # 步骤 3：模拟用户安装
    if ! simulate_install /tmp/remote-claude-0.2.12.tgz; then
        log_error "npm install 失败，终止测试"
        exit 1
    fi

    # 步骤 4：验证 postinstall 执行
    if ! verify_postinstall; then
        log_error "postinstall 验证失败，终止测试"
        exit 1
    fi

    # 步骤 5：测试基本命令
    if ! test_basic_commands "$install_dir"; then
        log_error "基本命令测试失败，继续执行..."
    fi

    # 步骤 6：文件完整性检查
    if ! check_file_integrity "$install_dir"; then
        log_error "文件完整性检查失败，继续执行..."
    fi

    # 步骤 7：生成测试报告
    generate_report

    # 步骤 8：清理
    cleanup

    # 输出最终结果
    print_results

    if [ $FAILED -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# 运行主流程
main "$@"
