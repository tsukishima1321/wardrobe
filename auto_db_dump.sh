#!/bin/bash

echo ----------------------------

source /etc/profile
source ~/.bashrc

dbname=wardrobe

time=$(date "+%Y%m%d%H%M%S")


temp_dir=$(mktemp -d)

openssl rand -base64 32 > $temp_dir/key.bin

pg_dump -d $dbname | openssl enc -aes-256-cbc -pbkdf2 -salt -pass file:$temp_dir/key.bin > $temp_dir/all.sql.enc

openssl pkeyutl -encrypt -inkey $wardrobe_backupdir/public_key.pem -pubin -in $temp_dir/key.bin -out $temp_dir/key.bin.enc

rm $temp_dir/key.bin

tar -czf $wardrobe_backupdir/backups/$time.tar.gz -C $temp_dir all.sql.enc key.bin.enc

rm -rf $temp_dir

psql -d $dbname -c "INSERT INTO backup_records (timestamp, comment) VALUES ('$time', '自动备份');"


echo $time
