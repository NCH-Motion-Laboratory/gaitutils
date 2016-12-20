# -*- coding: utf-8 -*-
"""
Created on Fri Nov 11 10:49:55 2016

@author: hus20664877
"""

    def read_normaldata(self):
        gcdfile = model.normaldata_path
        if gcdfile:
            if not os.path.isfile(gcdfile):
                raise Exception('Cannot find specified normal data file')
            f = open(gcdfile, 'r')
            lines = f.readlines()
            f.close()
            # normaldata variables are named as in the file. the model should have a corresponding map.
            normaldata = {}
            for li in lines:
                if li[0] == '!':  # it's a variable name
                    thisvar = li[1:li.find(' ')]  # set dict key
                    normaldata[thisvar] = list()
                # it's a number, so read into list
                elif li[0].isdigit() or li[0] == '-':
                    normaldata[thisvar].append([float(x) for x in li.split()])
            self.normaldata.update(normaldata)
