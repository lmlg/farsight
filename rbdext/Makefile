CFLAGS += -O2 -g -D_GNU_SOURCE
OBJS = bdev_rbd.o bdev_rbd_rpc.o
SPDK = /opt/mellanox/spdk
DEPS = -lrbd -lspdk_json -lspdk_bdev -lspdk -lspdk_env_dpdk -lrte_mempool -lrte_bus_pci

all: libxrbd.so

%.o: %.c
	gcc -I$(SPDK)/include $(CFLAGS) -Wl,-rpath=$(SPDK)/lib -fPIC -c $< -o $@

libxrbd.so: $(OBJS)
	gcc -fPIC -shared $(CFLAGS) -L$(SPDK)/lib -Wl,-rpath=$(SPDK)/lib -o $@ $(OBJS) $(DEPS)

clean:
	rm -rf *.o libxrbd*

