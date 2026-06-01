"""
Hermes Skills Validator — 基于 Skill Forge 的质量检测思路
验证 Hermes skills 的 frontmatter 和结构

Quality Gates:
1. Frontmatter validator — 检查 name, description, version (semver)
2. Structure validator — 检查 ## 章节存在且非空
3. Change detection — 基于内容 hash 而非时间戳
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional

import yaml

# ============ Constants (参考 Skill Forge) ============

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

HERMES_SKILLS_DIR = Path.home() / ".hermes" / "skills"
VALIDATION_CACHE = Path.home() / ".hermes" / "skills" / ".validation_cache.json"


# ============ Quality Gates (参考 Skill Forge validator.py) ============

def validate_frontmatter(path: Path) -> tuple[bool, str]:
    """验证 YAML frontmatter：name, description, version (必须是 semver)"""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, f"Cannot read file: {e}"

    fm_match = FRONTMATTER_RE.match(content)
    if not fm_match:
        if content.startswith("---") and "\n---" in content[:10]:
            return False, "Empty frontmatter (no YAML content between --- markers)"
        return False, "Missing YAML frontmatter (file must start with ---\\n...\\n---\\n)"

    try:
        frontmatter = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}"

    if frontmatter is None:
        return False, "Empty frontmatter"
    if not isinstance(frontmatter, dict):
        return False, f"Frontmatter must be a YAML mapping, got {type(frontmatter).__name__}"

    missing = []
    for field in ("name", "description", "version"):
        if field not in frontmatter or not str(frontmatter[field]).strip():
            missing.append(field)

    if missing:
        return False, f"Missing required field(s): {', '.join(missing)}"

    version = str(frontmatter["version"])
    if not SEMVER_RE.match(version):
        return False, f"Invalid version '{version}' — must be semver (e.g., 1.0.0)"

    return True, "Frontmatter valid"


def validate_structure(path: Path) -> tuple[bool, str]:
    """验证 SKILL.md 有有意义的 ## 章节"""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, f"Cannot read file: {e}"

    fm_match = FRONTMATTER_RE.match(content)
    body = content[fm_match.end():] if fm_match else content

    headings = re.findall(r"^## (.+)$", body, re.MULTILINE)

    if not headings:
        return False, "No ## sections found"

    # 检查空章节
    warnings = []
    for heading in headings:
        pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
        section_match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
        if section_match:
            section_body = section_match.group(1).strip()
            if not section_body:
                warnings.append(f"Section '## {heading}' is empty")
            elif len(section_body) < 30:
                warnings.append(f"Section '## {heading}' is very short ({len(section_body)} chars)")

    if warnings:
        return True, f"Structure OK with {len(warnings)} warning(s): {'; '.join(warnings[:3])}"

    return True, f"Structure valid ({len(headings)} sections)"


def validate_skill(path: Path) -> list[dict]:
    """运行所有质量检测"""
    results = []

    passed, details = validate_frontmatter(path)
    results.append({"check_name": "frontmatter", "passed": passed, "details": details})

    passed, details = validate_structure(path)
    results.append({"check_name": "structure", "passed": passed, "details": details})

    return results


# ============ Content Hash (参考 Skill Forge importer.py) ============

def compute_content_hash(path: Path) -> str:
    """计算文件内容 hash（用于检测实际修改）"""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def load_validation_cache() -> dict:
    """加载验证缓存"""
    if VALIDATION_CACHE.exists():
        try:
            return json.loads(VALIDATION_CACHE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_validation_cache(cache: dict) -> None:
    """保存验证缓存"""
    try:
        VALIDATION_CACHE.write_text(json.dumps(cache, indent=2))
    except OSError:
        pass


def validate_all_skills() -> dict:
    """验证所有 skills，基于内容 hash 检测变更"""
    cache = load_validation_cache()
    results = []
    stats = {"total": 0, "passed": 0, "failed": 0, "changed": 0, "new": 0}

    if not HERMES_SKILLS_DIR.exists():
        return {"error": f"Skills dir not found: {HERMES_SKILLS_DIR}", "results": [], "stats": stats}

    skill_dirs = [d for d in HERMES_SKILLS_DIR.rglob("*") if d.is_dir() and (d / "SKILL.md").exists()]

    for skill_dir in sorted(skill_dirs):
        skill_md = skill_dir / "SKILL.md"
        skill_name = skill_dir.name
        stats["total"] += 1

        current_hash = compute_content_hash(skill_md)
        cached = cache.get(skill_name)

        if cached and cached.get("hash") == current_hash:
            # 无变更，使用缓存结果
            results.append({
                "name": skill_name,
                "path": str(skill_md),
                "from_cache": True,
                "checks": cached.get("checks", []),
                "all_passed": cached.get("all_passed", False),
            })
            if cached.get("all_passed"):
                stats["passed"] += 1
            else:
                stats["failed"] += 1
            continue

        # 重新验证
        checks = validate_skill(skill_md)
        all_passed = all(c["passed"] for c in checks)

        results.append({
            "name": skill_name,
            "path": str(skill_md),
            "from_cache": False,
            "checks": checks,
            "all_passed": all_passed,
        })

        if all_passed:
            stats["passed"] += 1
        else:
            stats["failed"] += 1

        if cached:
            stats["changed"] += 1
        else:
            stats["new"] += 1

        # 更新缓存
        cache[skill_name] = {
            "hash": current_hash,
            "checks": checks,
            "all_passed": all_passed,
            "validated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    save_validation_cache(cache)

    return {"results": results, "stats": stats}


def show_failed_only(results: dict, limit: int = 10) -> None:
    """只显示失败的 skills"""
    failed = [r for r in results["results"] if not r["all_passed"]]

    if not failed:
        print("✅ All skills passed validation!")
        return

    print(f"\n❌ {len(failed)} skills failed quality gates:\n")
    for r in failed[:limit]:
        print(f"  {r['name']}")
        for check in r["checks"]:
            if not check["passed"]:
                print(f"    - {check['check_name']}: {check['details']}")
    if len(failed) > limit:
        print(f"  ... and {len(failed) - limit} more")


if __name__ == "__main__":
    import sys

    print("🔍 Validating Hermes skills...")
    print()

    results = validate_all_skills()

    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)

    stats = results["stats"]
    print(f"Total: {stats['total']} | ✅ Passed: {stats['passed']} | ❌ Failed: {stats['failed']}")
    if stats["changed"]:
        print(f"Changed (re-validated): {stats['changed']} | New: {stats['new']}")

    show_failed_only(results)

    # 退出码：0=全部通过, 1=有失败
    sys.exit(0 if stats["failed"] == 0 else 1)