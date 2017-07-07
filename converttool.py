i#coding:utf8

sci_to_str(sciStr):
    '''科学计数法转换成字符串'''
    assert type('str')==type(sciStr),'invalid format'
    if 'E' not in sciStr:
        return sciStr
    s = '%.8f' % float(sciStr)
    while '0' == s[-1] and '.' in s:
        s = s[:-1]
    if '.' == s[-1]:
        s = s[:-1]
    return s
