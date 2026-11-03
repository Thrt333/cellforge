# At most two targets: verified peer for this attachment, then complete ARP rows.
function valid(ip, a, n) {
    n=split(ip,a,".")
    return n==4 && a[1]==192 && a[2]==168 && a[3]==225 && a[4] ~ /^[0-9]+$/ && a[4]>1 && a[4]<255
}
BEGIN { if (valid(cached)) { print cached; seen[cached]=1; count=1 } }
$6=="bridge0" && $3=="0x2" && valid($1) && !seen[$1] && count<2 {
    print $1; seen[$1]=1; count++
}
