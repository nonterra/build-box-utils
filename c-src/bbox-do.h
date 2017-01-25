#ifndef BBOX_H_INCLUDED
#define BBOX_H_INCLUDED

#define BBOX_VERSION "1.0.0"
#define BBOX_ERR_INVOCATION 1
#define BBOX_ERR_RUNTIME    2

/* Config */

#define BBOX_DO_MOUNT_DEV  1
#define BBOX_DO_MOUNT_PROC 2
#define BBOX_DO_MOUNT_SYS  4
#define BBOX_DO_MOUNT_HOME 8
#define BBOX_DO_MOUNT_ALL  0x0F

#include <sys/types.h>

typedef struct {
    char *target_dir;
    char *home_dir;
    unsigned int do_mount;
} bbox_conf_t;

bbox_conf_t *bbox_config_new();
int bbox_config_set_target_dir(bbox_conf_t *conf, const char *path);
char *bbox_config_get_target_dir(const bbox_conf_t *conf);
int bbox_config_set_home_dir(bbox_conf_t *conf, const char *path);
char *bbox_config_get_home_dir(const bbox_conf_t *conf);
void bbox_config_clear_mount(bbox_conf_t *c);
void bbox_config_set_mount_all(bbox_conf_t *c);
void bbox_config_set_mount_dev(bbox_conf_t *c);
void bbox_config_set_mount_proc(bbox_conf_t *c);
void bbox_config_set_mount_sys(bbox_conf_t *c);
void bbox_config_set_mount_home(bbox_conf_t *c);
void bbox_config_unset_mount_dev(bbox_conf_t *c);
void bbox_config_unset_mount_proc(bbox_conf_t *c);
void bbox_config_unset_mount_sys(bbox_conf_t *c);
void bbox_config_unset_mount_home(bbox_conf_t *c);
unsigned int bbox_config_get_mount_any(const bbox_conf_t *c);
unsigned int bbox_config_get_mount_dev(const bbox_conf_t *c);
unsigned int bbox_config_get_mount_proc(const bbox_conf_t *c);
unsigned int bbox_config_get_mount_sys(const bbox_conf_t *c);
unsigned int bbox_config_get_mount_home(const bbox_conf_t *c);
void bbox_config_free(bbox_conf_t *conf);

/* Utilities */

void bbox_path_join(char **buf_ptr, const char *base, const char *sub,
        size_t *n_ptr);
void bbox_perror(char *lead, char *msg, ...);
int bbox_runas_fetch_output(uid_t uid, const char *cmd, char * const argv[],
        char **out_buf, size_t *out_buf_size);

/* Mounting */

int bbox_mount_any(const bbox_conf_t *conf, const char *sys_root);
int bbox_mount_is_mounted(const char *path);

/* Commands */

int bbox_list(int argc, char * const argv[]);
int bbox_login(int argc, char * const argv[]);
int bbox_run(int argc, char * const argv[]);
int bbox_mount(int argc, char * const argv[]);
int bbox_umount(int argc, char * const argv[]);

#endif
