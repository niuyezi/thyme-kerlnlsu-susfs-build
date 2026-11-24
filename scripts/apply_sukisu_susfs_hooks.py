#!/usr/bin/env python3
"""Apply SukiSU-Ultra (builtin) + SuSFS inline hooks cleanly for crDroid 15.0 (4.19.325)."""

from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, target: str, replacement: str, label: str) -> str:
    count = text.count(target)
    if count != 1:
        raise RuntimeError(f"[{label}] expected 1 match for anchor, got {count}:\n{target}")
    return text.replace(target, replacement, 1)


def patch_namei(root: pathlib.Path) -> None:
    p = root / "fs" / "namei.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    static_sig = "static int filename_lookup(int dfd, struct filename *name, unsigned flags,"
    nonstatic_sig = "int filename_lookup(int dfd, struct filename *name, unsigned flags,"
    if static_sig in txt:
        txt = replace_once(txt, static_sig, nonstatic_sig, "fs/namei.c filename_lookup")
        p.write_text(txt, encoding="utf-8")
        print("[+] fs/namei.c: exposed filename_lookup as non-static")
    elif nonstatic_sig in txt:
        print("[=] fs/namei.c: filename_lookup already non-static")
    else:
        raise RuntimeError("[fs/namei.c] could not locate filename_lookup definition")


def patch_kernelsu_419(root: pathlib.Path) -> None:
    # 1. Guard <linux/static_call.h> (introduced in Linux 5.10)
    inc = root / "KernelSU" / "kernel" / "kernel_includes.h"
    txt = inc.read_text(encoding="utf-8", errors="replace")
    target = "#include <linux/static_call.h>\n"
    guarded = (
        "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n"
        "#include <linux/static_call.h>\n"
        "#endif\n"
    )
    if guarded not in txt and target in txt:
        inc.write_text(
            replace_once(txt, target, guarded, "KernelSU kernel_includes.h static_call guard"),
            encoding="utf-8",
        )
        print("[+] KernelSU/kernel/kernel_includes.h: guarded <linux/static_call.h> for < 5.10")

    # 2. Fix 2-arg access_ok() in kpm.c for Linux < 5.0 (which requires access_ok(VERIFY_WRITE, addr, size))
    kpm = root / "KernelSU" / "kernel" / "extension" / "kpm" / "kpm.c"
    kpm_txt = kpm.read_text(encoding="utf-8", errors="replace")
    kpm_old = "    if (!access_ok(u64_to_user_ptr(cmd.result_code), sizeof(result))) return -EFAULT;"
    kpm_new = (
        "#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 0, 0)\n"
        "    if (!access_ok(VERIFY_WRITE, u64_to_user_ptr(cmd.result_code), sizeof(result))) return -EFAULT;\n"
        "#else\n"
        "    if (!access_ok(u64_to_user_ptr(cmd.result_code), sizeof(result))) return -EFAULT;\n"
        "#endif"
    )
    if "VERIFY_WRITE" not in kpm_txt and kpm_old in kpm_txt:
        kpm.write_text(replace_once(kpm_txt, kpm_old, kpm_new, "KernelSU kpm.c access_ok 4.19"), encoding="utf-8")
        print("[+] KernelSU/kernel/extension/kpm/kpm.c: fixed access_ok() for < 5.0")

    # 3. Use ksu_strncpy_from_user_nofault() compat wrapper in sulog/event.c
    sulog = root / "KernelSU" / "kernel" / "sulog" / "event.c"
    sulog_txt = sulog.read_text(encoding="utf-8", errors="replace")
    sulog_old = "            strncpy_from_user_nofault(arg, (const void __user *)untagged_addr((unsigned long)arg_user), sizeof(arg));"
    sulog_new = "            ksu_strncpy_from_user_nofault(arg, (const void __user *)untagged_addr((unsigned long)arg_user), sizeof(arg));"
    if sulog_old in sulog_txt:
        sulog.write_text(replace_once(sulog_txt, sulog_old, sulog_new, "KernelSU sulog/event.c nofault wrapper"), encoding="utf-8")
        print("[+] KernelSU/kernel/sulog/event.c: switched to ksu_strncpy_from_user_nofault()")

    # 4. Suppress -Wunused-variable for 5.10+-only pol/old_pol in selinux/rules.c
    rules = root / "KernelSU" / "kernel" / "selinux" / "rules.c"
    rules_txt = rules.read_text(encoding="utf-8", errors="replace")
    rules_old = "void apply_kernelsu_rules(void)\n{\n    struct selinux_policy *pol, *old_pol;\n"
    rules_new = "void apply_kernelsu_rules(void)\n{\n    struct selinux_policy __maybe_unused *pol, __maybe_unused *old_pol;\n"
    if rules_old in rules_txt:
        rules.write_text(replace_once(rules_txt, rules_old, rules_new, "KernelSU selinux/rules.c unused var"), encoding="utf-8")
        print("[+] KernelSU/kernel/selinux/rules.c: marked pol/old_pol __maybe_unused")


def patch_namespace(root: pathlib.Path) -> None:
    p = root / "fs" / "namespace.c"
    rej = root / "fs" / "namespace.c.rej"
    orig = root / "fs" / "namespace.c.orig"
    txt = p.read_text(encoding="utf-8", errors="replace")

    if "#define CL_COPY_MNT_NS" not in txt:
        txt = replace_once(
            txt,
            "#include <linux/sched/task.h>\n\n"
            "#include \"pnode.h\"\n"
            "#include \"internal.h\"\n",
            "#include <linux/sched/task.h>\n"
            "#ifdef CONFIG_KSU_SUSFS\n"
            "#include <linux/susfs_def.h>\n"
            "#endif // #ifdef CONFIG_KSU_SUSFS\n\n"
            "#include \"pnode.h\"\n"
            "#include \"internal.h\"\n\n"
            "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
            "extern bool susfs_is_current_ksu_domain(void);\n"
            "extern struct static_key_true susfs_is_sdcard_android_data_not_decrypted;\n\n"
            "#define CL_COPY_MNT_NS BIT(25) /* used by copy_mnt_ns() */\n\n"
            "#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n",
            "fs/namespace.c OPLUS_SECURE_GUARD header conflict fix",
        )
        p.write_text(txt, encoding="utf-8")
        print("[+] fs/namespace.c: resolved header hunk cleanly")

    if rej.exists():
        rej_txt = rej.read_text(encoding="utf-8", errors="replace")
        # Only remove .rej if it exclusively contains the single header hunk we just applied
        if rej_txt.count("@@") == 2 and "CL_COPY_MNT_NS BIT(25)" in rej_txt:
            rej.unlink()
            if orig.exists():
                orig.unlink()
            print("[+] fs/namespace.c.rej: cleared resolved header reject")
        else:
            print("[!] fs/namespace.c.rej contains unexpected hunks; leaving .rej intact")


def patch_exec(root: pathlib.Path) -> None:
    p = root / "fs" / "exec.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "ksu_handle_execveat_sucompat" in txt:
        print("[=] fs/exec.c: already hooked")
        return

    txt = replace_once(
        txt,
        "#include <linux/vmalloc.h>\n",
        "#include <linux/vmalloc.h>\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "#include <linux/susfs_def.h>\n"
        "#endif\n",
        "fs/exec.c include",
    )

    txt = replace_once(
        txt,
        "static int __do_execve_file(int fd, struct filename *filename,\n",
        "#ifdef CONFIG_KSU_SUSFS\n"
        "extern bool ksu_su_compat_enabled;\n"
        "extern struct static_key_true susfs_is_sdcard_android_data_not_decrypted;\n"
        "extern bool __ksu_is_allow_uid_for_current(uid_t uid);\n"
        "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr, void *argv,\n"
        "\t\t\tvoid *envp, int *flags);\n"
        "extern int ksu_handle_execveat_sucompat(int *fd, struct filename **filename_ptr, void *argv,\n"
        "\t\t\t\tvoid *envp, int *flags);\n"
        "extern int ksu_handle_post_execveat_sucompat(int *fd, struct filename **filename_ptr, void *argv,\n"
        "\t\t\tvoid *envp, int *flags, int *retval);\n"
        "#endif\n"
        "static int __do_execve_file(int fd, struct filename *filename,\n",
        "fs/exec.c externs",
    )

    txt = replace_once(
        txt,
        "\tstruct files_struct *displaced;\n"
        "\tint retval;\n\n"
        "\tif (IS_ERR(filename))\n"
        "\t\treturn PTR_ERR(filename);\n",
        "\tstruct files_struct *displaced;\n"
        "\tint retval;\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tbool is_su_session = false;\n"
        "#endif\n\n"
        "\tif (IS_ERR(filename))\n"
        "\t\treturn PTR_ERR(filename);\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tif (likely(susfs_is_current_proc_no_su()))\n"
        "\t\tgoto orig_flow;\n"
        "\tif (likely(ksu_su_compat_enabled) && likely(filename)) {\n"
        "\t\tif (static_branch_unlikely(&susfs_is_sdcard_android_data_not_decrypted))\n"
        "\t\t\tis_su_session = !ksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
        "\t\telse\n"
        "\t\t\tis_su_session = !ksu_handle_execveat_sucompat(&fd, &filename, &argv, &envp, &flags);\n"
        "\t}\n"
        "orig_flow:\n"
        "#endif\n",
        "fs/exec.c __do_execve_file pre-hook",
    )

    txt = replace_once(
        txt,
        "\tfree_bprm(bprm);\n"
        "\tkfree(pathbuf);\n"
        "\tif (filename)\n"
        "\t\tputname(filename);\n",
        "\tfree_bprm(bprm);\n"
        "\tkfree(pathbuf);\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tif (unlikely(is_su_session))\n"
        "\t\t(void)ksu_handle_post_execveat_sucompat(&fd, &filename, &argv, &envp, &flags, &retval);\n"
        "#endif\n"
        "\tif (filename)\n"
        "\t\tputname(filename);\n",
        "fs/exec.c __do_execve_file post-hook",
    )

    p.write_text(txt, encoding="utf-8")
    print("[+] fs/exec.c: hooked cleanly")


def patch_open(root: pathlib.Path) -> None:
    p = root / "fs" / "open.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "ksu_handle_faccessat" in txt:
        print("[=] fs/open.c: already hooked")
        return

    txt = replace_once(
        txt,
        "#include <linux/compat.h>\n",
        "#include <linux/compat.h>\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "#include <linux/susfs_def.h>\n"
        "#endif\n",
        "fs/open.c include",
    )

    txt = replace_once(
        txt,
        "long do_faccessat(int dfd, const char __user *filename, int mode)\n",
        "#ifdef CONFIG_KSU_SUSFS\n"
        "extern bool ksu_su_compat_enabled;\n"
        "extern bool __ksu_is_allow_uid_for_current(uid_t uid);\n"
        "extern int ksu_handle_faccessat(int *dfd, struct filename **filename, int *mode,\n"
        "\t\t\tint *flags);\n"
        "extern int filename_lookup(int dfd, struct filename *name, unsigned flags,\n"
        "\t\t\t\tstruct path *path, struct path *root);\n"
        "#endif\n"
        "long do_faccessat(int dfd, const char __user *filename, int mode)\n",
        "fs/open.c externs",
    )

    txt = replace_once(
        txt,
        "\tint res;\n"
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n"
        "\tif (mode & ~S_IRWXO)",
        "\tint res;\n"
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tstruct filename *fname = NULL;\n"
        "#endif\n\n"
        "\tif (mode & ~S_IRWXO)",
        "fs/open.c fname local",
    )

    txt = replace_once(
        txt,
        "\told_cred = override_creds(override_cred);\n"
        "retry:\n"
        "\tres = user_path_at(dfd, filename, lookup_flags, &path);\n"
        "\tif (res)\n"
        "\t\tgoto out;\n",
        "\told_cred = override_creds(override_cred);\n"
        "retry:\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tfname = getname_flags(filename, lookup_flags, NULL);\n\n"
        "\tif (likely(susfs_is_current_proc_no_su()))\n"
        "\t\tgoto orig_flow;\n\n"
        "\tif (likely(ksu_su_compat_enabled)) {\n"
        "\t\tif (unlikely(__ksu_is_allow_uid_for_current(current_uid().val)))\n"
        "\t\t\tksu_handle_faccessat(&dfd, &fname, &mode, NULL);\n"
        "\t}\n\n"
        "orig_flow:\n"
        "\tres = filename_lookup(dfd, fname, lookup_flags, &path, NULL);\n"
        "#else\n"
        "\tres = user_path_at(dfd, filename, lookup_flags, &path);\n"
        "#endif\n"
        "\tif (res)\n"
        "\t\tgoto out;\n",
        "fs/open.c do_faccessat lookup",
    )

    p.write_text(txt, encoding="utf-8")
    print("[+] fs/open.c: hooked cleanly")


def patch_read_write(root: pathlib.Path) -> None:
    p = root / "fs" / "read_write.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "ksu_handle_sys_read" in txt:
        print("[=] fs/read_write.c: already hooked")
        return

    txt = replace_once(
        txt,
        "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n"
        "{\n"
        "\treturn ksys_read(fd, buf, count);\n"
        "}\n",
        "#ifdef CONFIG_KSU\n"
        "extern struct static_key_true ksu_is_init_rc_hook_enabled;\n"
        "extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd, char __user **buf_ptr, size_t *count_ptr);\n"
        "#endif\n"
        "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n"
        "{\n"
        "#ifdef CONFIG_KSU\n"
        "\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))\n"
        "\t\tksu_handle_sys_read(fd, &buf, &count);\n"
        "#endif\n"
        "\treturn ksys_read(fd, buf, count);\n"
        "}\n",
        "fs/read_write.c read syscall",
    )

    p.write_text(txt, encoding="utf-8")
    print("[+] fs/read_write.c: hooked cleanly")


def patch_stat(root: pathlib.Path) -> None:
    p = root / "fs" / "stat.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "ksu_handle_stat" in txt:
        print("[=] fs/stat.c: already hooked")
        return

    txt = replace_once(
        txt,
        "#include <asm/unistd.h>\n",
        "#include <asm/unistd.h>\n"
        "#include \"internal.h\"\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "#include <linux/susfs_def.h>\n"
        "#include \"mount.h\"\n"
        "extern struct static_key_true ksu_is_init_rc_hook_enabled;\n"
        "extern void ksu_handle_vfs_fstat(int fd, loff_t *kstat_size_ptr);\n"
        "extern bool ksu_su_compat_enabled;\n"
        "extern bool __ksu_is_allow_uid_for_current(uid_t uid);\n"
        "extern int ksu_handle_stat(int *dfd, struct filename **filename, int *flags);\n"
        "#endif\n",
        "fs/stat.c include and externs",
    )

    txt = replace_once(
        txt,
        "\t\terror = vfs_getattr(&f.file->f_path, stat,\n"
        "\t\t\t\t    request_mask, query_flags);\n"
        "\t\tfdput(f);\n",
        "\t\terror = vfs_getattr(&f.file->f_path, stat,\n"
        "\t\t\t\t    request_mask, query_flags);\n"
        "\t\tfdput(f);\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\t\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))\n"
        "\t\t\tksu_handle_vfs_fstat(fd, &stat->size);\n"
        "#endif\n",
        "fs/stat.c vfs_statx_fd",
    )

    txt = replace_once(
        txt,
        "\tint error = -EINVAL;\n"
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n",
        "\tint error = -EINVAL;\n"
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tstruct filename *fname = NULL;\n"
        "\textern int filename_lookup(int dfd, struct filename *name, unsigned flags,\n"
        "\t\t\t\t\tstruct path *path, struct path *root);\n"
        "#endif\n",
        "fs/stat.c vfs_statx locals",
    )

    txt = replace_once(
        txt,
        "retry:\n"
        "\terror = user_path_at(dfd, filename, lookup_flags, &path);\n"
        "\tif (error)\n"
        "\t\tgoto out;\n",
        "retry:\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tfname = getname_flags(filename, lookup_flags, NULL);\n\n"
        "\tif (likely(susfs_is_current_proc_no_su()))\n"
        "\t\tgoto orig_flow;\n\n"
        "\tif (likely(ksu_su_compat_enabled)) {\n"
        "\t\tif (unlikely(__ksu_is_allow_uid_for_current(current_uid().val)))\n"
        "\t\t\tksu_handle_stat(&dfd, &fname, &flags);\n"
        "\t}\n\n"
        "orig_flow:\n"
        "\terror = filename_lookup(dfd, fname, lookup_flags, &path, NULL);\n"
        "#else\n"
        "\terror = user_path_at(dfd, filename, lookup_flags, &path);\n"
        "#endif\n"
        "\tif (error)\n"
        "\t\tgoto out;\n",
        "fs/stat.c vfs_statx lookup",
    )

    p.write_text(txt, encoding="utf-8")
    print("[+] fs/stat.c: hooked cleanly")


def patch_sys(root: pathlib.Path) -> None:
    p = root / "kernel" / "sys.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "ksu_handle_setresuid" in txt:
        print("[=] kernel/sys.c: already hooked")
        return

    txt = replace_once(
        txt,
        "SYSCALL_DEFINE3(setresuid, uid_t, ruid, uid_t, euid, uid_t, suid)\n"
        "{\n"
        "\treturn __sys_setresuid(ruid, euid, suid);\n"
        "}\n",
        "#ifdef CONFIG_KSU\n"
        "extern int ksu_handle_setresuid(uid_t ruid, uid_t euid, uid_t suid);\n"
        "#endif\n"
        "SYSCALL_DEFINE3(setresuid, uid_t, ruid, uid_t, euid, uid_t, suid)\n"
        "{\n"
        "#ifdef CONFIG_KSU_SUSFS\n"
        "\tif (ksu_handle_setresuid(ruid, euid, suid))\n"
        "\t\tpr_info(\"Something wrong with ksu_handle_setresuid()\\n\");\n"
        "#endif\n"
        "\treturn __sys_setresuid(ruid, euid, suid);\n"
        "}\n",
        "kernel/sys.c setresuid",
    )

    p.write_text(txt, encoding="utf-8")
    print("[+] kernel/sys.c: hooked cleanly")


def patch_reboot(root: pathlib.Path) -> None:
    p = root / "kernel" / "reboot.c"
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "ksu_handle_sys_reboot" in txt:
        print("[=] kernel/reboot.c: already hooked")
        return

    txt = replace_once(
        txt,
        "SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,\n"
        "\t\tvoid __user *, arg)\n"
        "{\n"
        "\tstruct pid_namespace *pid_ns = task_active_pid_ns(current);\n"
        "\tchar buffer[256];\n"
        "\tint ret = 0;\n\n",
        "#ifdef CONFIG_KSU\n"
        "extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg);\n"
        "#endif\n"
        "SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,\n"
        "\t\tvoid __user *, arg)\n"
        "{\n"
        "\tstruct pid_namespace *pid_ns = task_active_pid_ns(current);\n"
        "\tchar buffer[256];\n"
        "\tint ret = 0;\n\n"
        "#ifdef CONFIG_KSU\n"
        "\tif (system_state == SYSTEM_RUNNING)\n"
        "\t\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
        "#endif\n\n",
        "kernel/reboot.c reboot syscall",
    )

    p.write_text(txt, encoding="utf-8")
    print("[+] kernel/reboot.c: hooked cleanly")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <kernel_root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    patch_kernelsu_419(root)
    patch_namespace(root)
    patch_namei(root)
    patch_exec(root)
    patch_open(root)
    patch_read_write(root)
    patch_stat(root)
    patch_reboot(root)
    patch_sys(root)
    print("[+] All SukiSU-Ultra + SuSFS inline hooks applied cleanly.")


if __name__ == "__main__":
    main()
