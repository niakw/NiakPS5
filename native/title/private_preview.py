#!/usr/bin/env python3
"""Render the REAL user-supplied PS4/PS5 bands/footers in native OpenGL locally.

GitHub's public preview intentionally uses original QA assets. This helper
replaces only the temporary HOST preview textures, never repository assets,
Sony title files, console data or PLDmgr configuration.
"""
from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def sibling_module(name:str):
    location=Path(__file__).resolve().with_name(name+".py")
    spec=spec_from_file_location("niak_"+name,location)
    if spec is None or spec.loader is None:
        raise RuntimeError("Missing NiakPS5 Python module: "+name)
    module=module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def stage_private_templates(kit:Path, archive:Path):
    installer=sibling_module("ftp_install")
    images=installer.load_private_template_zip(archive)
    if set(images)!=set(installer.TEMPLATE_NAMES):
        missing=set(installer.TEMPLATE_NAMES)-set(images)
        raise ValueError("Six exact PS4/PS5 templates required; missing: "+
                         ", ".join(sorted(missing)))
    target=kit/"assets"/"niak-preview-templates"
    target.mkdir(parents=True,exist_ok=True)
    for name,content in sorted(images.items()):
        (target/name).write_bytes(content)
    return target

def render_private_preview(kit:Path, archive:Path, output:Path):
    if not (kit/"host"/"snapshot_main.cpp").is_file():
        raise ValueError("Host renderer kit absent. Build NiakPS5 first.")
    main=kit/"host"/"snapshot_main.cpp"
    if "NIAK_CASE_TOUR" not in main.read_text("utf-8"):
        sibling_module("host_preview").patch(kit)  # One-time patch of pinned upstream OpenGL host renderer.
    fixtures=stage_private_templates(kit,archive)
    env=os.environ.copy()
    env.update({
        "LIBGL_ALWAYS_SOFTWARE":"1",
        "EGL_PLATFORM":"surfaceless",
        "GALLIUM_DRIVER":"llvmpipe",
        "NIAK_CASE_TEMPLATE_ASSETS":str(fixtures.resolve()),
        "NIAK_CASE_PREVIEW_ASSETS":str((kit/"assets"/"niak-preview-cases").resolve()),
        "NIAK_CASE_PREVIEW_MEDIA":str((kit/"assets"/"niak-preview-media").resolve()),
    })
    driver=kit/"tools"/"host-snapshots.sh"
    if not driver.is_file():
        raise ValueError("Pinned OpenGL snapshot driver absent")
    output.mkdir(parents=True,exist_ok=True)
    command=["bash",str(driver),str(output),"aurora","1920","1080"]
    subprocess.run(command,env=env,check=True,cwd=ROOT)
    env["NIAK_CASE_TOUR"]="1"
    subprocess.run(command,env=env,check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/"native/title/validate_preview.py"),
                    str(output)],check=True,cwd=ROOT)
    print("PRIVATE CASE PREVIEW: PASS")
    print("Real immutable PS4/PS5 templates used:",fixtures)
    print("Preview screenshots:",output)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates-zip",type=Path,required=True,
                        help="User's private six-template ZIP; never uploaded")
    parser.add_argument("--kit",type=Path,
                        default=ROOT/".build"/"ps5-title-kit")
    parser.add_argument("--output",type=Path,
                        default=ROOT/"build"/"niak-preview-private")
    args=parser.parse_args()
    render_private_preview(args.kit.resolve(),args.templates_zip.resolve(),
                           args.output.resolve())

if __name__=="__main__":
    main()
