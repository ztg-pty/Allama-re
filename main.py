import os
import sys
import subprocess
import importlib
from pathlib import Path
import _runtime.logger as app_logger


def check_and_install_deps():
    missing = []
    for pkg in ["PySide6", "psutil"]:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return True

    print(f"发现缺失依赖: {', '.join(missing)}")
    print("正在自动安装...")

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
            *missing,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"依赖安装失败: {e}")
        print("请手动执行: pip install PySide6 psutil")
        return False


def main():
    app_logger.init_logging()
    logger = app_logger.get_logger("main")
    logger.info("应用启动")
    if not check_and_install_deps():
        input("\n按回车键退出...")
        return
    exe_dir = Path(__file__).parent
    models_dir = exe_dir / "models"
    if not models_dir.exists():
        models_dir.mkdir(parents=True, exist_ok=True)

    try:
        from llama import main as llama_main
        llama_main()
    except ImportError as e:
        logger.error(f"导入 llama.py 失败: {e}")
        print("请确保 llama.py 与 main.py 在同一目录下")
        input("\n按回车键退出...")
    except Exception as e:
        logger.error(f"运行出错: {e}")
        print(f"运行出错: {e}")
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()

