# Docker 目录说明

本目录只存放 Docker 回归所需的镜像、Compose 配置与脚本。

- 完整测试流程、命令说明、产物说明：见 [../docs/docker-test.md](../docs/docker-test.md)
- 本目录主要文件：
  - `Dockerfile.test`
  - `docker-compose.test.yml`
  - `scripts/docker-test.sh`
  - `scripts/docker-diagnose.sh`

如果你是在排查 Docker 回归，请优先阅读 `../docs/docker-test.md`，避免与旧副本文档产生偏差。
