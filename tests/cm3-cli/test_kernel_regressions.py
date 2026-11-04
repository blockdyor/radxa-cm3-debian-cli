"""Small compiler regressions, not a kernel or package build."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class KernelCompilerRegressions(unittest.TestCase):
    @unittest.skipUnless(shutil.which('aarch64-linux-gnu-gcc') and shutil.which('make'),
                         'targeted ARM64 compiler not installed')
    def test_clean_lp64_probe_uses_target_flags_not_amd64_environment(self):
        # Exact LP64 expression: pinned kernel tools/scripts/Makefile.arch:37.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Makefile').write_text(
                'LP64 := $(shell echo __LP64__ | ${CC} ${CFLAGS} -E -x c - | tail -n 1)\n'
                'clean:\n\t@test "$(LP64)" = 1\n')
            command = ['make', '-sC', directory, 'clean', 'CC=aarch64-linux-gnu-gcc']
            env = os.environ | {'CFLAGS': '-O2 -fcf-protection=full'}
            before = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertIn('fcf-protection', before.stderr)
            after = subprocess.run(command + ['CFLAGS=-O2 -mbranch-protection=standard'],
                                   env=env, capture_output=True, text=True)
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertNotIn('error:', after.stderr)

    @unittest.skipUnless(shutil.which('gcc'), 'C compiler not installed')
    def test_backported_allocation_order_gcc14_and_overflow_equivalence(self):
        support = subprocess.run(['gcc', '-Werror=calloc-transposed-args', '-x', 'c',
                                  '-fsyntax-only', os.devnull], capture_output=True)
        if support.returncode:
            self.skipTest('GCC does not support calloc-transposed-args diagnostic')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = r'''#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#define GFP_KERNEL 0x40
static size_t count, size;
static unsigned flags;
static int dummy;
static void *kvcalloc(size_t n, size_t s, unsigned f) __attribute__((alloc_size(1,2)));
static void *kvcalloc(size_t n, size_t s, unsigned f) {
 size_t product;
 count=n; size=s; flags=f;
 return __builtin_mul_overflow(n,s,&product) ? NULL : &dummy;
}
struct clone_root { uint64_t root; void *pointer; };
struct ctx { struct clone_root *clone_roots; };
struct args { uint64_t clone_sources_count; };
static int allocate(struct ctx *sctx, struct args *arg) {
 sctx->clone_roots = kvcalloc(arg->clone_sources_count + 1,
                            sizeof(*sctx->clone_roots), GFP_KERNEL);
 if (!sctx->clone_roots) return -12;
 return 0;
}
int main(void) {
 struct ctx ctx;
 struct args arg;
 uint64_t cases[] = {0,1,1024,SIZE_MAX/sizeof(struct clone_root),UINT64_MAX};
 for(size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
  arg.clone_sources_count=cases[i];
  size_t n=arg.clone_sources_count+1, a, b;
  int overflow=__builtin_mul_overflow(n,sizeof(struct clone_root),&a);
  assert(allocate(&ctx,&arg)==(overflow ? -12 : 0));
  assert(count==n && size==sizeof(struct clone_root) && flags==GFP_KERNEL);
  assert(__builtin_mul_overflow(sizeof(struct clone_root),n,&b)==overflow);
  if(!overflow) assert(a==b);
 }
 return 0;
}
'''
            path = root / 'allocation.c'
            path.write_text(source)
            command = ['gcc', '-O2', '-Wall', '-Wextra', '-Werror',
                       '-Werror=calloc-transposed-args', str(path), '-o', str(root / 'allocation')]
            subprocess.run(command, check=True, capture_output=True)
            subprocess.run([str(root / 'allocation')], check=True)
            path.write_text(source.replace(
                'kvcalloc(arg->clone_sources_count + 1,\n                            sizeof(*sctx->clone_roots),',
                'kvcalloc(sizeof(*sctx->clone_roots),\n                            arg->clone_sources_count + 1,'))
            before = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(before.returncode, 0)
            self.assertIn('calloc-transposed-args', before.stderr)


if __name__ == '__main__':
    unittest.main()
