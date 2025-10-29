#!/bin/bash

# Show logs live
exec journalctl -u picserver -f
