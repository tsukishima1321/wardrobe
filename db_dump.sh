#!/bin/sh

source /etc/profile
source ~/.bashrc

dbname=$closet_db_name

time=$(date "+%Y%m%d%H%M%S")


temp_dir=$(mktemp -d)

openssl rand -base64 32 > $temp_dir/key.bin

pg_dump -d $dbname | openssl enc -aes-256-cbc -pbkdf2 -salt -pass file:$temp_dir/key.bin > $temp_dir/all.sql.enc

openssl pkeyutl -encrypt -inkey $backupdir/public_key.pem -pubin -in $temp_dir/key.bin -out $temp_dir/key.bin.enc

rm $temp_dir/key.bin

tar -czf $backupdir/backups/$time.tar.gz -C $temp_dir all.sql.enc key.bin.enc

rm -rf $temp_dir

echo $time
