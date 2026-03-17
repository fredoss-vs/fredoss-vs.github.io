HOSTS=("10.0.0.126" "10.0.0.127" "10.0.0.128")

for HOST in "${HOSTS[@]}"; do
    echo "===== $HOST ====="

    ssh -i "$SSH_KEY" \
        -o StrictHostKeyChecking=no \
        -o BatchMode=yes \
        ${REMOTE_USER}@${HOST} 'bash -s' << 'EOF'

sudo apt update -y
sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y
sudo apt autoremove -y
sudo apt autoclean

EOF

done