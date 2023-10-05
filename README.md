# farsight

farsight is a client/server application that allows users to implement block devices
without the need for kernel modules by extending a very simple interface.

# installation

As with most python packages, it suffices to call the setup script:

```shell
python3 setup.py install
```

Afterwards, we may use the server module within the 'farsight' package. We need
to provide a configuration file for it. The chosen format is TOML, because of
its simplicity and portability.

## configuring the server
The server must specify the sections: "snap" and "server".

### server parameters
There are 2 parameters: "host" and "port", which define where the server will
be listening for incoming requests.

### snap parameters
The "snap" section needs to specify some parameters about NVIDIA's SNAP runtime.
This section must contain the following: "service_name", which sets the service
name as seen by systemd; "dpu_dir", which specifies the directory where the DPU
files have been installed by this package (this one should normally not be modified);
"service_file", which indicates where the systemd service file is located and
"num_pf", which represents the number of physical functions the DPU has.

### rbd dependencies
In order to compile the RBD backend, the server must have the necessary
libraries included. They can be installed by the system's package manager.
For example, on Ubuntu, you may run something like this:

```shell
apt install python3-rados python3-rbd
```

For more information, see here:
<https://docs.ceph.com/en/latest/rados/api/python/>
<https://docs.ceph.com/en/latest/rbd/api/librbdpy/>

Note that if those libraries aren't present, the server won't be able to
use the RBD backend, but it will still be able to boot up and run.

## Example files
In the "examples" directory there is an example configuration file for the server.

# usage
With the application installed and configured, we can now use the client and
server:

```shell
python3 -m farsight.server <path_to_config_file>
```

Assuming everything goes well, the server will block indefinitely while
handling incoming requests. It can be interrupted by signals to stop its
execution.

The server will most likely need root permissions, as it needs to call out
to SNAP.
