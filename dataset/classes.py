import operator

with open("infos.csv") as infos:
    data = infos.readlines()
    recorder = {}
    for line in data:
        titres, artists, types = line.strip('\n').split(';')
        types = types.split('_')
        for t in types:
            if t in  recorder:
                recorder[t].append(titres + "_" + artists)
            else:
                recorder[t] = [titres + "_" + artists]
    # print(dict(sorted(recorder.items(), key=lambda item: item[1])))
    print(recorder["anime rock"])
    
    # with open('new_infos.csv', 'w+') as new_infos:
    #     for line in data:
    #         titres, artists, types = line.strip('\n').split(';')
    #         types = types.split('_')
    #         new_types = {genre: recorder[genre] for genre in types}
    #         genre = max(new_types.items(), key=operator.itemgetter(1))[0]
    #         new_line = titres + ';' + artists + ';' + genre + '\n'
    #         new_infos.write(new_line)

