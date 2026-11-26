# 常用命令。Windows 上可直接用 `python tools/xxx.py`，不依赖 make。
PY ?= python

.PHONY: help doctor test test-quick release zip examples sync install clean bridge

help:
	@echo "make doctor    环境体检（python / java / jar / 知识库）"
	@echo "make test      全量回归（49 项）"
	@echo "make test-quick 跳过依赖 Java 的用例"
	@echo "make bridge    编译 Java 外观桥（需要 JDK 21+）"
	@echo "make release   发布检查 + 生成 dist zip"
	@echo "make examples  重新生成示例电路"
	@echo "make sync      把插件技能同步到 ~/.workbuddy/skills"
	@echo "make install   注册本地插件市场"
	@echo "make clean     清理构建产物与缓存"

bridge:
	$(PY) tools/build_bridge.py

doctor:
	$(PY) server/server.py --doctor

test:
	$(PY) tools/selftest.py

test-quick:
	$(PY) tools/selftest.py --quick

release:
	$(PY) tools/check_release.py --build

zip:
	$(PY) tools/build_zip.py

examples:
	$(PY) examples/generate.py

sync:
	$(PY) tools/sync_skill.py --apply

install:
	$(PY) tools/install.py

clean:
	$(PY) -c "import shutil,glob,os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True)]; [os.remove(p) for p in glob.glob('*.pyc')]; shutil.rmtree('dist', ignore_errors=True)"
