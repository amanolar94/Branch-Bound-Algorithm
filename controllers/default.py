    # -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

# -------------------------------------------------------------------------
# This is a sample controller
# - index is the default action of any application
# - user is required for authentication and authorization
# - download is for downloading files uploaded in the db (does streaming)
# -------------------------------------------------------------------------


def index():
    return dict()

def params():
    form=SQLFORM.factory(
        Field('vars',label=T('Select number of variables'),type='int',requires=(IS_NOT_EMPTY(),IS_INT_IN_RANGE(2, 10,error_message='Input must be an integer between 2 and 10'))),
        Field('con',label=T('Select number of constraints'),type='int',requires=(IS_NOT_EMPTY(),IS_INT_IN_RANGE(1, 10,error_message='Input must be an integer between 1 and 10')))

        )
    if form.process(dbio=False).accepted:
        variables=int(form.vars.vars)+1
        constraints=int(form.vars.con)+1
        redirect(URL('create_problem',vars=dict(vars=variables,cons=constraints)))
    return dict(form=form)


def create_problem():
    import json
    try:

        variables=int(request.vars['vars'])
        constraints=int(request.vars['cons'])
              
    except Exception as e:
        redirect(URL('index'))
        return dict()

    fields=[]
    fields.append(Field('probtype',label=T('Problem Type'),requires=IS_IN_SET({'LpMaximize':'Maximize','LpMinimize':'Minimize'},zero=None)))
    varnames=[]
    for i in range(1, variables):
        fields.append(Field('x_{va}'.format(va=i),label='x_{va}'.format(va=i),requires=(IS_NOT_EMPTY(),IS_FLOAT_IN_RANGE(None, None,error_message='Input must be a decimal number'))))
    for i in range(1, constraints):
        for j in range(1, variables):
            fields.append(Field('c_{co}x_{va}'.format(co=i,va=j),label='x_{va}'.format(va=j),requires=(IS_NOT_EMPTY(),IS_FLOAT_IN_RANGE(None, None,error_message='Input must be a decimal number'))))
        fields.append(Field('cotype_{co}'.format(co=i),requires=IS_IN_SET({'<=':'≤','=':'=','>=':'≥'},zero=None)))
        fields.append(Field('b_{co}'.format(co=i),requires=(IS_NOT_EMPTY(),IS_FLOAT_IN_RANGE(None, None,error_message='Input must be a decimal number'))))
    form=SQLFORM.factory(*fields,table_name='problem_variables')
    if form.process().accepted:
            redirect(URL('solution',vars=dict(problem=json.dumps(form.vars),variables=variables,constraints=constraints)))
    return dict(form=form,vars=variables,cos=constraints)

def solution():
    import json
    from pulp import *
    from treelib import Node, Tree
    import math
    import random
    try:

        variables=int(request.vars['variables'])
        constraints=int(request.vars['constraints'])
              
    except Exception as e:
        redirect(URL('index'))
        return dict()
    problem=json.loads(request.vars['problem'])    
    if problem['probtype']=='LpMaximize':
        probtype=LpMaximize
    else:
        probtype=LpMinimize
    # problem define
    prob = LpProblem("Branch & Bound", probtype )
    variableslist=[]
    objective=''
    for i in range(1,variables):
        variableslist.append(LpVariable('x_{no}'.format(no=i),0)) #create the variables
        objective+=variableslist[i-1]*problem['x_{var}'.format(var=i)] #objective function define
    prob+=objective, "obj" #final objective function
    constraint=[]
    #constraints declare
    for i in range(1,constraints):
        constraint=variableslist[0]*problem['c_{con}x_1'.format(con=i)] 
        for j in range(2,variables):
            constraint+=variableslist[j-1]*problem['c_{con}x_{var}'.format(con=i,var=j)]
        if problem['cotype_{con}'.format(con=i)]=='<=':
            prob+= constraint <= problem['b_{con}'.format(con=i)]  
        elif problem['cotype_{con}'.format(con=i)]=='>=':
            prob+= constraint >= problem['b_{con}'.format(con=i)]
        else:
            prob+= constraint == problem['b_{con}'.format(con=i)]
    prob.solve() #Solve initial LP
    if LpStatus[prob.status]!='Optimal': #if solution is not optimal we are done. It is either "Not Solved" or "Infeasible" or "Unbounded" or "Undefined"
        return dict(result=LpStatus[prob.status],example='none',variables=variables-1)
    # We create the tree for the branch and bound
    tree=Tree()
    Result={} #result of the problem
    Result['obj']=value(prob.objective)
    node_list=[] #list of node names
    best_node={} #best node every time
    best_node['node']='none'
    best_node['limit']=-float('inf')
    non_int_variables=[] #non int variables of current problem
    solution=True
    Result['vars']={}
    for v in prob.variables(): 
        Result['vars'][v.name]='{var}={value}'.format(var=v.name,value=v.varValue)
        Result[v.name]=v.varValue
        if not Result[v.name].is_integer():
            solution=False  # We find that there is a non-integer variable
            non_int_variables.append(v.name)
    if solution==True: # All variables in the solution are integers so we have the solution
        best_node['node']='original'
        best_node['limit']=value(prob.objective)
        best_node['result']=Result
    else:
        node_list.append('original')
    tree.create_node('Original','original',data={'status':LpStatus[prob.status],'problem':prob,'non_int':non_int_variables,'result':Result}) # First node is the original problem
    p=0
    while node_list:
        #for every node that we examine we create 2 new nodes based on the two new constraints that we inserted each for a the new problem
        solution=True
        branch_node=node_list[0] # We select the last inserted node for branching. We use the FIFO method for selecting the node.
        node_list.remove(branch_node) # And then we remove it from the nodes to be examined
        non_integer_variables=tree.get_node('{node}'.format(node=branch_node)).data['non_int'] # we get the non_integer variables from the node
        branch_variable=random.choice(non_integer_variables) # And then we randomly select which of them to cut for branch and bound
        down=int(tree.get_node('{node}'.format(node=branch_node)).data['result'][branch_variable]) #up and down limits for the new constraint
        up=math.ceil(tree.get_node('{node}'.format(node=branch_node)).data['result'][branch_variable])
        temp=tree.get_node('{node}'.format(node=branch_node)).data['problem'].copy() # We take the node problem and we create the new one with the new constraint
        var_index=int(branch_variable.split('_')[1])-1
        temp+=variableslist[var_index]<=down
        new_constraint='{x}<={bs}'.format(x=variableslist[var_index],bs=down)
        temp.solve()
        Result={}
        Result['vars']={}
        non_int_variables=[]
        if LpStatus[temp.status]=='Optimal':
            Result['obj']=value(temp.objective)
            for v in temp.variables():
                Result['vars'][v.name]='{var}={value}'.format(var=v.name,value=v.varValue)
                Result[v.name]=v.varValue
                if not Result[v.name].is_integer():
                    solution=False
                    non_int_variables.append(v.name)
            if solution==False:
                if best_node['node']=='none': #If we don't have a solution for now or....
                    node_list.append('node{no}'.format(no=p))
                else:
                    if problem['probtype']=='LpMaximize': #If we already have a solution already we have to find if our current objective function solution is better than our limit
                        if Result['obj']>best_node['limit']:
                            node_list.append('node{no}'.format(no=p))
                    else:
                        if Result['obj']<best_node['limit']:
                            node_list.append('node{no}'.format(no=p))
            else: #in case that we have a solution we have to compare it with the limit
                if problem['probtype']=='LpMaximize':
                    if Result['obj']>best_node['limit']:
                            best_node['node']='node{no}'.format(no=p)
                            best_node['limit']=Result['obj']
                            best_node['result']=Result
                else:
                    if Result['obj']<best_node['limit']:
                        best_node['node']='node{no}'.format(no=p)
                        best_node['limit']=Result['obj']
                        best_node['result']=Result
            tree.create_node('node{no}'.format(no=p),'node{no}'.format(no=p),parent='{node}'.format(node=branch_node),data={'status':LpStatus[temp.status],'problem':temp,'non_int':non_int_variables,'result':Result,'new_constraint':new_constraint})
        else:
            tree.create_node('node{no}'.format(no=p),'node{no}'.format(no=p),parent='{node}'.format(node=branch_node),data={'status':LpStatus[temp.status],'problem':temp,'non_int':non_int_variables,'result':{'obj':LpStatus[temp.status]},'new_constraint':new_constraint})

        p+=1
        temp=tree.get_node('{node}'.format(node=branch_node)).data['problem'].copy()
        temp+=variableslist[var_index]>=up
        new_constraint='{x}>={bs}'.format(x=variableslist[var_index],bs=up)
        temp.solve()
        Result={}
        Result['vars']={}
        non_int_variables=[]
        solution=True
        if LpStatus[temp.status]=='Optimal':
            Result['obj']=value(temp.objective)
            for v in temp.variables():
                Result['vars'][v.name]='{var}={value}'.format(var=v.name,value=v.varValue)
                Result[v.name]=v.varValue
                if not Result[v.name].is_integer():
                    solution=False
                    non_int_variables.append(v.name)
            if solution==False:
                if best_node['node']=='none': #If we don't have a solution for now or....
                    node_list.append('node{no}'.format(no=p))
                else:
                    if problem['probtype']=='LpMaximize': #If we already have a solution we already have to find if our current objective function solution is better than our limit
                        if Result['obj']>best_node['limit']:
                            node_list.append('node{no}'.format(no=p))
                    else:
                        if Result['obj']<best_node['limit']:
                            node_list.append('node{no}'.format(no=p))
            else: #in case that we have a solution we have to compare it with the limit
                if problem['probtype']=='LpMaximize':
                    if Result['obj']>best_node['limit']:
                            best_node['node']='node{no}'.format(no=p)
                            best_node['limit']=Result['obj']
                            best_node['result']=Result
                else:
                    if Result['obj']<best_node['limit']:
                        best_node['node']='node{no}'.format(no=p)
                        best_node['limit']=Result['obj']
                        best_node['result']=Result
            tree.create_node('node{no}'.format(no=p),'node{no}'.format(no=p),parent='{node}'.format(node=branch_node),data={'status':LpStatus[temp.status],'problem':temp,'non_int':non_int_variables,'result':Result,'new_constraint':new_constraint})
        else:
            tree.create_node('node{no}'.format(no=p),'node{no}'.format(no=p),parent='{node}'.format(node=branch_node),data={'status':LpStatus[temp.status],'problem':temp,'non_int':non_int_variables,'result':{'obj':LpStatus[temp.status]},'new_constraint':new_constraint})

        p+=1
    
    for node in tree.all_nodes():
        node.data.pop('problem',None)
        node.data.pop('non_int',None)
    tree_data=[]
    node_list=tree.all_nodes()
    for node in range(0,len(node_list)):
        if not node_list[node].is_root():
            if node_list[node].data['result']['obj'] == 'Infeasible': 
                temp_list=[{'v':node_list[node].identifier,'f':'<div style="font-size:0.8em">{new}</div>{obj}'.format(new=node_list[node].data['new_constraint'],obj=node_list[node].data['result']['obj'])},tree.parent(node_list[node].identifier).identifier,'']
            else:
                if node_list[node].identifier==best_node['node']:
                    temp_list=[{'v':node_list[node].identifier,'f':'<div class="best"> <div style="font-size:0.8em">{new}</div>z={obj}<div style="color:red; font-style:italic">{vars}</div></div>'.format(new=node_list[node].data['new_constraint'],obj=node_list[node].data['result']['obj'], vars=str(node_list[node].data['result']['vars'].values()))},tree.parent(node_list[node].identifier).identifier,'']
                else:
                    temp_list=[{'v':node_list[node].identifier,'f':'<div style="font-size:0.8em">{new}</div>z={obj}<div style="color:red; font-style:italic">{vars}</div>'.format(new=node_list[node].data['new_constraint'],obj=node_list[node].data['result']['obj'], vars=str(node_list[node].data['result']['vars'].values()))},tree.parent(node_list[node].identifier).identifier,'']

        else:
            temp_list=[{'v':node_list[node].identifier,'f':'z={obj}<div style="color:red; font-style:italic">{vars}</div>'.format(obj=node_list[node].data['result']['obj'],vars=str(node_list[node].data['result']['vars'].values()))},'','']
        tree_data.append(temp_list)
    
    return dict(result='Feasible',example=tree_data,variables=variables-1)

